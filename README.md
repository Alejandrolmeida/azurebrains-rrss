# Azurebrains RRSS

Agente de publicación automática multicanal para el ecosistema [Azurebrains](https://blog.azurebrains.com). Detecta nuevo contenido publicado en el blog (posts y noticias), genera copy adaptado por red social, crea tarjetas visuales y publica en **X, LinkedIn, Instagram y Facebook** de forma event-driven desde el pipeline del blog.

## Stack

- **Runtime**: Python 3.12 (Azure Functions / Container App)
- **Orquestación**: GitHub Actions (workflow `announce.yml` en `azurebrains-blog`)
- **Generación de copy**: Azure OpenAI `gpt-4o-mini` (existente: `oai-azurebrains-blog`)
- **Generación de imágenes**: Azure OpenAI `gpt-image-1` / DALL-E 3 (existente)
- **Media hosting**: Azure Blob Storage público (`rrss-media` container)
- **Idempotencia / auditoría**: Azure Cosmos DB (colección nueva en `cosmos-azurebrains-chat-hlnywnla`)
- **Secretos**: Azure Key Vault (`kv-azrbrnsblog`, existente)
- **IaC**: Bicep
- **CI/CD**: GitHub Actions (OIDC secretless)

## Paneles conectados

| Sistema | Integración |
|---------|-------------|
| **azurebrains-blog** | Genera `manifest.json` en cada build. El workflow `announce.yml` lee diferencias. |
| **azurebrains-admin** | Dashboard nuevo "RRSS" con estado de publicaciones, errores y métricas por red. |
| **azurebrains-chat** | Comandos vía chat: publicar manualmente, reprogramar, ver auditoría. |

## Redes soportadas

| Red | API | Estado |
|-----|-----|--------|
| X (Twitter) | X API v2 — `POST /2/tweets` | Planificado |
| LinkedIn | Posts API REST + versioned headers | Planificado |
| Instagram | Graph API — IG User Media | Planificado |
| Facebook | Pages API — `/{page-id}/feed` | Planificado |

## Estructura del repo

```
azurebrains-rrss/
├── README.md
├── PLAN.md                     ← Documento de planificación del proyecto
├── mcp.json                    ← Configuración MCP servers para Copilot
├── .github/
│   └── agents/
│       └── azure-foundry.agent.md  ← Agente Azure Foundry (IaC y arquitectura)
├── src/                        ← Código del publisher (next sprint)
│   ├── publisher/              ← Publicadores por plataforma
│   ├── formatters/             ← Formateo de copy por red
│   └── db/                     ← Capa de idempotencia / Cosmos DB
├── bicep/                      ← Infraestructura como código
│   ├── main.bicep
│   └── parameters/
└── docs/                       ← Documentación técnica
```

## Quick Start (cuando esté implementado)

```bash
# Instalar dependencias
pip install -r requirements.txt

# Desarrollo local
cp .env.example .env  # Rellenar tokens de RRSS y secretos
python -m src.main

# Deploy
az deployment sub create \
  --location spaincentral \
  --template-file bicep/main.bicep \
  --parameters bicep/parameters/prod.json
```

## Documentación

- [PLAN.md](PLAN.md) — Planificación completa del proyecto
- [docs/deep-research-report.md](docs/deep-research-report.md) — Investigación técnica previa de viabilidad
- [docs/viabilidad-rrss-research.pdf](docs/viabilidad-rrss-research.pdf) — Informe PDF de viabilidad original
