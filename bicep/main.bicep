// ─────────────────────────────────────────────────────────────────────────────
// bicep/main.bicep — Azurebrains RRSS Publisher
//
// Despliega los recursos Azure nuevos necesarios para el publisher de RRSS:
//   - Azure Container App (runtime del publisher)
//   - Azure Container Apps Environment
//   - Azure Blob Storage (hosting público de tarjetas visuales)
//   - Managed Identity + RBAC (acceso a Cosmos DB, Key Vault, Storage)
//
// Recursos compartidos (existentes, NO se despliegan aquí):
//   - Azure OpenAI: oai-azurebrains-blog    (rg: azurebrains-blog)
//   - Cosmos DB:    cosmos-azurebrains-chat-hlnywnla (rg: rg-azurebrains-chatapp)
//   - Key Vault:    kv-azrbrnsblog          (rg: azurebrains-blog)
//
// Uso:
//   az group create --name rg-azurebrains-blog --location spaincentral
//   az deployment group create \
//     --resource-group azurebrains-blog \
//     --template-file bicep/main.bicep \
//     --parameters bicep/parameters/prod.json
// ─────────────────────────────────────────────────────────────────────────────

@description('Entorno: dev | prod')
param environment string = 'prod'

@description('Región de despliegue')
param location string = resourceGroup().location

@description('Tags aplicados a todos los recursos')
param tags object = {
  Project: 'azurebrains-rrss'
  Environment: environment
  ManagedBy: 'Bicep'
  Owner: 'alejandro@globalai.es'
}

@description('Nombre del recurso Azure Container Registry (para pull de imagen)')
param acrName string

@description('Nombre del Key Vault existente donde están los secretos de RRSS')
param keyVaultName string = 'kv-azrbrnsblog'

@description('Resource Group del Key Vault existente')
param keyVaultResourceGroup string = 'azurebrains-blog'

@description('Cosmos DB account name (existente)')
param cosmosAccountName string = 'cosmos-azurebrains-chat-hlnywnla'

@description('Resource Group del Cosmos DB existente')
param cosmosResourceGroup string = 'rg-azurebrains-chatapp'

// ─── Variables de naming ─────────────────────────────────────────────────────

var suffix = uniqueString(resourceGroup().id)
var storageAccountName = 'stazrbrnsmedia${take(suffix, 6)}'
var containerAppEnvName = 'cae-azurebrains-rrss-${environment}'
var containerAppName = 'ca-azurebrains-rrss-${environment}'
var identityName = 'id-azurebrains-rrss-${environment}'

// ─── Managed Identity ────────────────────────────────────────────────────────

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

// ─── Azure Blob Storage (tarjetas visuales) ──────────────────────────────────

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: true // El container rrss-media es público (imágenes para RRSS)
    publicNetworkAccess: 'Enabled'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storage
  name: 'default'
}

resource mediaContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'rrss-media'
  properties: {
    publicAccess: 'Blob' // Acceso público de lectura a blobs (imágenes)
  }
}

// ─── RBAC: Managed Identity → Storage Blob Data Contributor ─────────────────

resource storageBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Container Apps Environment ──────────────────────────────────────────────

resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppEnvName
  location: location
  tags: tags
  properties: {
    zoneRedundant: false
  }
}

// ─── Container App ───────────────────────────────────────────────────────────

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    environmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'http'
        corsPolicy: {
          allowedOrigins: ['https://blog.azurebrains.com']
          allowedMethods: ['POST']
          allowedHeaders: ['Authorization', 'Content-Type']
        }
      }
      registries: [
        {
          server: '${acrName}.azurecr.io'
          identity: identity.id
        }
      ]
      secrets: [
        {
          name: 'publisher-secret-token'
          keyVaultUrl: 'https://${keyVaultName}.vault.azure.net/secrets/rrss-publisher-secret-token'
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'publisher'
          image: '${acrName}.azurecr.io/azurebrains-rrss:latest'
          env: [
            { name: 'ENVIRONMENT', value: environment }
            { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storage.name }
            { name: 'AZURE_STORAGE_CONTAINER', value: 'rrss-media' }
            { name: 'KEY_VAULT_URL', value: 'https://${keyVaultName}.vault.azure.net/' }
            { name: 'COSMOS_ENDPOINT', value: 'https://${cosmosAccountName}.documents.azure.com:443/' }
            { name: 'PUBLISHER_SECRET_TOKEN', secretRef: 'publisher-secret-token' }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
        rules: [
          {
            name: 'http-scaling'
            http: { metadata: { concurrentRequests: '10' } }
          }
        ]
      }
    }
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

@description('URL del Publisher Service (endpoint para el workflow announce.yml)')
output publisherUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'

@description('URL base del Azure Blob Storage para medios')
output mediaBaseUrl string = 'https://${storage.name}.blob.core.windows.net/rrss-media'

@description('Principal ID de la Managed Identity (para asignar roles adicionales)')
output identityPrincipalId string = identity.properties.principalId
