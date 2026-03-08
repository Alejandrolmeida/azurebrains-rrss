# Azurebrains RRSS — Plan de Proyecto

Publicador automático multicanal para el ecosistema Azurebrains.  
Detecta nuevo contenido (posts y noticias) generado por el blog y lo anuncia de forma autónoma en **X, LinkedIn, Facebook e Instagram**.

> **Estado de cuentas (marzo 2026)**: X ✅, LinkedIn ✅ y Facebook ✅ existen bajo la marca Azurebrains pero necesitan un **lavado de cara visual** (logo, banner, bio). Instagram ⚠️ — estado pendiente de confirmar.

---

## Contexto y recursos del ecosistema

### Repositorios del proyecto

| Repo | Descripción | Relación con RRSS |
|------|-------------|-------------------|
| `azurebrains-blog` | Jekyll blog + pipeline de 6 agentes de IA | **Fuente de contenido**. Genera `_site/manifest.json` en cada build |
| `azurebrains-admin` | Dashboard Next.js + Azure SWA | **Consumidor**. Panel "RRSS" mostrará estado de publicaciones |
| `azurebrains-chat` | Agente conversacional Chainlit | **Consumidor**. Comandos manuales: publicar, reprogramar, auditar |
| `azurebrains-rrss` | **Este repo**. Publisher de RRSS | Orquestador del ciclo de publicación |

### Infraestructura Azure compartida (existente)

| Recurso | Nombre | Resource Group | Estado |
|---------|--------|----------------|--------|
| Azure OpenAI | `oai-azurebrains-blog` | `azurebrains-blog` | ✅ ACTIVO |
| ↳ Modelo copy | `gpt-4o-mini` | — | ✅ DESPLEGADO |
| ↳ Modelo imágenes | `dall-e-3` / `gpt-image-1` | — | ✅ DESPLEGADO |
| AI Search | `srch-azurebrains-blog` | `azurebrains-blog` | ✅ ACTIVO |
| Key Vault | `kv-azrbrnsblog` | `azurebrains-blog` | ✅ ACTIVO |
| Cosmos DB | `cosmos-azurebrains-chat-hlnywnla` | `rg-azurebrains-chatapp` | ✅ ACTIVO |
| App Service (chat) | `app-azurebrains-chat-prod` | `rg-azurebrains-chatapp` | ✅ ACTIVO |
| Static Web App (admin) | SWA `azurebrains-admin` | — | ✅ ACTIVO |

### Nuevos recursos Azure necesarios

| Recurso | Nombre propuesto | Resource Group | Propósito |
|---------|-----------------|----------------|-----------|
| Blob Storage (public) | `stazrbrnsmedia` | `azurebrains-blog` | Hosting de tarjetas visuales para Instagram/Facebook |
| Cosmos DB collection (nueva) | `rrss` en `cosmos-azurebrains-chat-hlnywnla` | `rg-azurebrains-chatapp` | Idempotencia y auditoría de publicaciones |
| Key Vault secrets (nuevos) | En `kv-azrbrnsblog` existente | `azurebrains-blog` | Tokens OAuth de X, LinkedIn, Meta |
| GitHub Actions secrets | Repo `azurebrains-rrss` + `azurebrains-blog` | GitHub | `PUBLISHER_ENDPOINT`, `PUBLISHER_TOKEN` |

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│          azurebrains-blog (Jekyll + GitHub Pages)               │
│  CI/CD: deploy.yml → build + generate manifest.json            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ on: push to main
                           ▼  (job: announce, after deploy)
┌─────────────────────────────────────────────────────────────────┐
│             announce.yml (GitHub Actions)                        │
│  1. Descarga manifest.json actual vs anterior (caché)           │
│  2. Calcula diff → lista de NewContentPublished                 │
│  3. Llama a Publisher API con cada item                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP POST → Publisher API
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│            Publisher Service (Azure Functions / Container)       │
│                                                                  │
│  ┌─────────────────┐    ┌──────────────────────────────────┐   │
│  │ Idempotency     │    │  Content Formatter               │   │
│  │ Check           │    │  (GPT-4o-mini via oai-*)         │   │
│  │ Cosmos DB rrss  │    │  - X: ≤280 chars + hashtags      │   │
│  └────────┬────────┘    │  - LinkedIn: article + thumbnail │   │
│           │ not seen    │  - Instagram: caption 2200       │   │
│           ▼             │  - Facebook: text + link         │   │
│  ┌─────────────────┐    └──────────────┬───────────────────┘   │
│  │ Social Card     │                   │                        │
│  │ Generator       │◄──────────────────┘                        │
│  │ (DALL-E 3 /     │                                            │
│  │  gpt-image-1)   │─── JPEG → stazrbrnsmedia (public URL)     │
│  └─────────────────┘                                            │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Queue / Scheduler                            │  │
│  │  - 2-4 slots/día por red           - Backoff + jitter     │  │
│  │  - Prioridad: news > post          - Max 3 reintentos     │  │
│  └──────┬───────────┬───────────────┬────────────────────┬───┘  │
│         ▼           ▼               ▼                    ▼      │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌─────────────┐   │
│  │Publisher │ │Publisher │ │  Publisher   │ │  Publisher  │   │
│  │    X     │ │ LinkedIn │ │  Instagram   │ │  Facebook   │   │
│  └────┬─────┘ └────┬─────┘ └──────┬───────┘ └──────┬──────┘   │
│       │            │               │                 │           │
│       └────────────┴───────────────┴─────────────────┘          │
│                             │                                    │
│                     ┌───────▼───────┐                           │
│                     │  Audit Log    │                           │
│                     │  Cosmos DB    │                           │
│                     │  (rrss coll.) │                           │
│                     └───────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
                           │ surfaceado en
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
  azurebrains-admin  azurebrains-chat  GitHub Actions
  (Panel RRSS)       (comandos chat)   (workflow log)
```

---

## Modelo de datos (Cosmos DB — colección `rrss`)

### Documento `content_item`
```json
{
  "id": "2026-03-08-nuevo-post",
  "type": "content_item",
  "canonical_url": "https://blog.azurebrains.com/2026/03/08/nuevo-post.html",
  "content_type": "post | news | workshop | manual",
  "title": "...",
  "excerpt": "...",
  "hero_media_url": "https://stazrbrnsmedia.blob.core.windows.net/rrss-media/2026-03-08-nuevo-post.jpg",
  "fingerprint": "<sha256 de canonical_url + published_at>",
  "published_at": "2026-03-08T10:00:00Z",
  "detected_at": "2026-03-08T10:05:00Z",
  "social_cards": {
    "x": "...", "linkedin": "...", "instagram": "...", "facebook": "..."
  }
}
```

### Documento `delivery_job`
```json
{
  "id": "<uuid>",
  "type": "delivery_job",
  "content_item_id": "2026-03-08-nuevo-post",
  "platform": "x | linkedin | instagram | facebook",
  "scheduled_for": "2026-03-08T11:00:00Z",
  "status": "pending | in_progress | published | failed | skipped",
  "idempotency_key": "<sha256(content_item_id + platform)>",
  "remote_post_id": null,
  "attempts": [],
  "copy": "...",
  "media_url": "..."
}
```

---

## Manifest del blog (formato de entrada)

El workflow del blog generará en cada build un fichero `_site/manifest.json`:

```json
{
  "generated_at": "2026-03-08T10:00:00Z",
  "items": [
    {
      "id": "2026-03-08-nuevo-post",
      "canonical_url": "https://blog.azurebrains.com/2026/03/08/nuevo-post.html",
      "title": "Título del post",
      "excerpt": "Resumen de 2-3 líneas...",
      "content_type": "post",
      "hero_image_url": "https://blog.azurebrains.com/assets/img/posts/2026-03-08-nuevo-post.jpg",
      "published_at": "2026-03-08T10:00:00Z",
      "tags": ["azure", "ai", "rag"],
      "needs_review": false
    }
  ]
}
```

> **Cambio necesario en `azurebrains-blog`**: añadir el script `scripts/build-manifest.js` y un paso en `deploy.yml` para generar y publicar `manifest.json` junto al sitio.

---

## Restricciones por plataforma (resumen operativo)

| Plataforma | Endpoint principal | Rate limit | Formato imagen | Límite copy | Cuenta |
|------------|-------------------|------------|----------------|-------------|--------|
| **X** | `POST /2/tweets` | 100/15 min por usuario | JPG/PNG/WEBP ≤5 MB | 280 chars | ✅ Existe (revisar visual) |
| **LinkedIn** | `POST /rest/posts` | No publicado (portal) | URN tras subida | 3.000 chars | ✅ Existe (revisar visual) |
| **Facebook** | `POST /{page-id}/feed` | >200 llamadas/h límite app | URL pública (cURL por Meta) | Sin límite práctico | ✅ Existe (revisar visual) |
| **Instagram** | `POST /{igUserId}/media` + `media_publish` | 100 API posts/24h | JPEG, 4:5→1.91:1 ratio, ≤8 MB | 2.200 chars + ≤30 hashtags | ⚠️ Por confirmar |

### Requisitos de cumplimiento por plataforma

| Plataforma | Requisito | Acción previa |
|------------|-----------|---------------|
| X | OAuth 2.0 PKCE user-context; refresh token | ~~Crear cuenta~~ ✅ · Crear app en X Developer Portal y generar tokens |
| LinkedIn | `w_member_social` + `w_organization_social`; cabecera `Linkedin-Version` | ~~Crear cuenta~~ ✅ · Crear app en LinkedIn Developers, aprobar permisos |
| Facebook | `pages_manage_posts`; Page Access Token | ~~Crear Page~~ ✅ · Crear app en Meta y vincular Page existente |
| Instagram | App Review + Business Verification; cuenta profesional vinculada a Page | ⚠️ Confirmar si existe cuenta; vincular a la Page de Facebook; App Review |

---

## Fases del proyecto

### FASE 0 — Preparación, lavado de cara y accesos (Semana 1)
> Objetivo: identidad visual unificada en las 3 redes confirmadas + accesos API + secretos en Key Vault.

#### 0.A — Lavado de cara visual (previo a cualquier publicación automatizada)

> Las cuentas de X, LinkedIn y Facebook existen pero seguramente tienen imagen desactualizada. Antes de publicar con el agente, conviene que las cuentas ya representen bien la marca.

- [ ] **0.A.1** Auditar estado actual de las 3 cuentas
  - Anotar: foto de perfil, banner/portada, bio/descripción, URL, nombre de usuario
  - Captura de pantalla del estado actual (referencia antes/después)

- [ ] **0.A.2** Preparar assets visuales de marca Azurebrains
  - **Logo**: versión cuadrada 400×400px (foto de perfil) y versión horizontal para banner
  - **Banner X**: 1500×500px — fondo de color de marca + tagline + URL del blog
  - **Banner LinkedIn**: 1584×396px — mismo estilo
  - **Portada Facebook**: 820×312px — mismo estilo
  - Fuente y paleta: las mismas que usa el blog (verificar en `_sass/` del blog)
  - Herramienta sugerida: Canva con plantillas o generación con `gpt-image-1` + edición

- [ ] **0.A.3** Actualizar perfil en **X** (`@azurebrains` o handle actual)
  - Subir foto de perfil y banner nuevos
  - Bio: máx. 160 chars — ej. _"Blog técnico sobre Azure AI, RAG y arquitectura multi-agente. Contenido generado por 6 agentes de IA 🤖 blog.azurebrains.com"_
  - URL: `https://blog.azurebrains.com`
  - Localización: Spain

- [ ] **0.A.4** Actualizar perfil en **LinkedIn** (Page o perfil personal)
  - Subir logo y banner
  - Descripción de empresa / tagline alineado con el blog
  - URL del sitio web: `https://blog.azurebrains.com`
  - Confirmar si es **Company Page** (requerida para `w_organization_social`) o perfil personal

- [ ] **0.A.5** Actualizar perfil en **Facebook Page**
  - Foto de perfil y portada
  - Descripción corta y larga
  - URL del blog en el campo "Sitio web"
  - Verificar que la Page es de tipo "Blog" o "Tecnología"

- [ ] **0.A.6** Confirmar y preparar **Instagram**
  - ⚠️ Verificar si existe cuenta de Instagram para Azurebrains
  - Si existe: convertir a cuenta **profesional/Business** y vincular a la Facebook Page
  - Si no existe: crear cuenta Business directamente vinculada a la Page
  - Actualizar bio, link in bio (`blog.azurebrains.com`), foto de perfil

---

#### 0.B — Registro de aplicaciones y accesos API

- [ ] **0.B.1** Crear aplicación en X Developer Portal
  - OAuth 2.0 user-context habilitado (la cuenta ya existe ✅)
  - Generar `X_ACCESS_TOKEN` y `X_REFRESH_TOKEN`
  - Guardar en `kv-azrbrnsblog`: `rrss-x-access-token`, `rrss-x-refresh-token`, `rrss-x-api-key`, `rrss-x-api-secret`

- [ ] **0.B.2** Crear aplicación en LinkedIn Developers
  - La cuenta/Page ya existe ✅
  - Permisos: `w_member_social`, `w_organization_social`
  - Producto: "Share on LinkedIn" + "Marketing Developer Platform" (si aplica)
  - Guardar en `kv-azrbrnsblog`: `rrss-linkedin-access-token`, `rrss-linkedin-client-id`, `rrss-linkedin-client-secret`
  - Anotar `LINKEDIN_AUTHOR_URN` (person o organization)

- [ ] **0.B.3** Crear aplicación en Meta (Facebook + Instagram)
  - La Facebook Page ya existe ✅; Instagram por confirmar (0.A.6)
  - Permisos: `instagram_basic`, `instagram_content_publish`, `pages_manage_posts`, `pages_read_engagement`
  - App Mode: Development → solicitar Standard Access cuando MVP validado
  - Guardar en `kv-azrbrnsblog`: `rrss-meta-access-token`, `rrss-meta-page-id`, `rrss-meta-ig-user-id`
  - Planificar Business Verification (requerida para Standard Access en Instagram)

- [ ] **0.B.4** Crear Blob Storage para media pública
  ```bash
  az storage account create \
    --name stazrbrnsmedia \
    --resource-group azurebrains-blog \
    --location spaincentral \
    --sku Standard_LRS \
    --allow-blob-public-access true
  
  az storage container create \
    --name rrss-media \
    --account-name stazrbrnsmedia \
    --public-access blob
  ```

- [ ] **0.B.5** Crear colección `rrss` en Cosmos DB existente
  - Cosmos: `cosmos-azurebrains-chat-hlnywnla`
  - Base de datos: `azurebrains` (o crear `rrss-db`)
  - Contenedores: `content_items` y `delivery_jobs`
  - Partition key: `/platform` (delivery_jobs) y `/content_type` (content_items)

- [ ] **0.B.6** Configurar GitHub Actions secrets en `azurebrains-rrss`
  - `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` (OIDC)
  - `KEY_VAULT_NAME=kv-azrbrnsblog`

---

### FASE 1 — Manifest en el blog (Semana 1-2)
> Objetivo: el blog genera y publica `manifest.json` en cada deploy.

- [ ] **1.1** Crear `scripts/build-manifest.js` en `azurebrains-blog`
  - Lee `_site/` y genera JSON con todos los posts + noticias
  - Incluye campos: `id`, `canonical_url`, `title`, `excerpt`, `content_type`, `hero_image_url`, `published_at`, `tags`
  - Detecta nuevos items comparando con `manifest-previous.json` (caché en GitHub Actions)

- [ ] **1.2** Añadir paso en `deploy.yml` del blog
  ```yaml
  - name: Generate manifest
    run: node scripts/build-manifest.js
  - name: Upload manifest artifact
    uses: actions/upload-artifact@v4
    with:
      name: manifest
      path: _site/manifest.json
  ```

- [ ] **1.3** Publicar `manifest.json` junto al sitio (accesible en `https://blog.azurebrains.com/manifest.json`)

- [ ] **1.4** Validar que el manifest se genera correctamente en PR de prueba
  - Verificar 5+ posts y 5+ noticias en el JSON
  - Comprobar que `published_at` coincide con el front matter de Jekyll

---

### FASE 2 — Publisher Service (Semana 2-3)
> Objetivo: servicio Python que recibe un `content_item` y publica en las redes.

- [ ] **2.1** Scaffold del proyecto en `azurebrains-rrss/src/`
  ```
  src/
  ├── publisher/
  │   ├── __init__.py
  │   ├── x_publisher.py         ← POST /2/tweets + media upload
  │   ├── linkedin_publisher.py  ← POST /rest/posts + asset upload
  │   ├── instagram_publisher.py ← container + media_publish
  │   └── facebook_publisher.py  ← POST /{page-id}/feed
  ├── formatters/
  │   ├── __init__.py
  │   └── copy_generator.py      ← GPT-4o-mini, prompt por red
  ├── media/
  │   ├── __init__.py
  │   ├── card_generator.py      ← DALL-E 3 / gpt-image-1 templates
  │   └── blob_uploader.py       ← Upload a stazrbrnsmedia
  ├── db/
  │   ├── __init__.py
  │   └── cosmos_client.py       ← Idempotencia + audit log
  └── main.py                    ← Azure Function / Container entrypoint
  ```

- [ ] **2.2** Implementar `copy_generator.py`
  - Prompt diferenciado por plataforma (X breve impactante, LinkedIn profesional, Instagram visual, Facebook conversacional)
  - Validación de longitudes antes de devolver
  - Variación controlada (evitar copy idéntico entre redes)

- [ ] **2.3** Implementar `card_generator.py`
  - Template: título + subtítulo + logo azurebrains + fondo de marca
  - Output: JPEG 1080x1080 (Instagram square) + 1200x630 (LinkedIn/Facebook/X card)
  - Modelo: `gpt-image-1` o DALL-E 3 con modo `edit` sobre plantilla base
  - Upload a `stazrbrnsmedia/rrss-media/{id}-square.jpg` y `{id}-wide.jpg`

- [ ] **2.4** Implementar `cosmos_client.py`
  - `check_idempotency(content_item_id, platform)` → bool
  - `mark_published(delivery_job)` → void
  - `log_attempt(job_id, status, remote_post_id, error)` → void

- [ ] **2.5** Implementar publicadores por plataforma
  - `x_publisher.py`:
    - OAuth 2.0 PKCE con refresh automático (token en Key Vault)
    - `POST /2/tweets` con `text` + `media.media_ids`
    - Manejo de `x-rate-limit-*` headers
  - `linkedin_publisher.py`:
    - Headers: `Linkedin-Version: YYYYMM`, `X-Restli-Protocol-Version: 2.0.0`
    - Subida de imagen: Images API → URN
    - `POST /rest/posts` con article + thumbnail
  - `instagram_publisher.py`:
    - `POST /{igUserId}/media` con `image_url` (URL pública de stazrbrnsmedia)
    - `POST /{igUserId}/media_publish` con `creation_id`
    - Preflight check: cURL de la imagen antes de crear contenedor
  - `facebook_publisher.py`:
    - Page Access Token desde flow de Meta
    - `POST /{pageId}/feed` con `message` + `link` + (opcional) `picture`

- [ ] **2.6** Tests de idempotencia
  - Ejecutar el mismo `content_item` 3 veces → sólo 1 publicación por plataforma
  - Verificar `idempotency_key` en Cosmos DB

---

### FASE 3 — Workflow de anuncio (Semana 3)
> Objetivo: el pipeline del blog dispara el publisher automáticamente.

- [ ] **3.1** Crear `announce.yml` en `azurebrains-blog/.github/workflows/`
  ```yaml
  name: Announce new content to RRSS
  
  on:
    workflow_run:
      workflows: ["Deploy to GitHub Pages"]
      types: [completed]
  
  jobs:
    announce:
      runs-on: ubuntu-latest
      if: ${{ github.event.workflow_run.conclusion == 'success' }}
      steps:
        - uses: actions/checkout@v4
        
        - name: Download manifest
          run: curl -s https://blog.azurebrains.com/manifest.json -o manifest-current.json
        
        - name: Restore previous manifest
          uses: actions/cache/restore@v4
          with:
            path: manifest-previous.json
            key: manifest-${{ github.sha }}
            restore-keys: manifest-
        
        - name: Detect new content
          run: node scripts/detect-new-content.js > new-items.json
        
        - name: Send to publisher
          env:
            PUBLISHER_ENDPOINT: ${{ secrets.PUBLISHER_ENDPOINT }}
            PUBLISHER_TOKEN: ${{ secrets.PUBLISHER_TOKEN }}
          run: node scripts/enqueue-new-content.js new-items.json
        
        - name: Save current manifest as previous
          uses: actions/cache/save@v4
          with:
            path: manifest-current.json
            key: manifest-${{ github.sha }}
  ```

- [ ] **3.2** Crear `scripts/detect-new-content.js` en el blog
  - Compara `manifest-current.json` vs `manifest-previous.json`
  - Output: JSON array de items nuevos
  - Incluye deduplicación por `fingerprint`

- [ ] **3.3** Crear `scripts/enqueue-new-content.js` en el blog
  - POST a `PUBLISHER_ENDPOINT` con cada item + `PUBLISHER_TOKEN`
  - Manejo de errores: log a stderr pero no bloquear el pipeline del blog

- [ ] **3.4** Test E2E con post de prueba
  - Crear post con `content_type: test` (ignorado en producción)
  - Verificar que fluye desde blog → manifest → announce → publisher → Cosmos

---

### FASE 4 — Integración con Admin y Chat (Semana 4)
> Objetivo: visibilidad desde azurebrains-admin y control desde azurebrains-chat.

- [ ] **4.1** Panel "RRSS" en `azurebrains-admin`
  - Tabla de `delivery_jobs` recientes con estado por plataforma
  - Métricas: publicaciones últimas 7 días, tasa de éxito por red, errores frecuentes
  - Alerta si token de alguna red está expirado
  - API Route: `/api/rrss/status` → lee de Cosmos DB colección `rrss`

- [ ] **4.2** Herramienta `rrss_status()` en `azurebrains-chat`
  - Tool del agente Chainlit que consulta el estado de las últimas publicaciones
  - Responde a: "¿Cómo van las publicaciones de hoy?" / "¿Hay errores en RRSS?"

- [ ] **4.3** Herramienta `trigger_rrss_publish()` en `azurebrains-chat`
  - Permite forzar publicación manual de un `content_item_id` en una red concreta
  - Llama al publisher con flag `force_override=True` (bypass idempotency)
  - Utilidad: republicar tras corrección de un error, publicar posts antiguos, probar

---

## Control de calidad y anti-spam

### Controles automáticos (ejecutados antes de encolar)

| Control | Implementación | Riesgo que mitiga |
|---------|----------------|-------------------|
| **Deduplicación por fingerprint** | SHA-256 de `canonical_url + published_at` en Cosmos DB | Re-ejecuciones del pipeline |
| **Deduplicación semántica** | Embeddings `text-embedding-3-small` + cosine similarity ≥0.92 → skip | Contenido muy similar en ventana 7 días |
| **Límites de longitud** | X ≤280 / LinkedIn ≤3000 / Instagram ≤2200 / Facebook ≤63.206 | Errores de API por exceso |
| **Variación de copy** | Prompt instruye variación; diferente hook, CTA y estructura por red | Flag "bulk/duplicative" de X y Meta |
| **Preflight media** | cURL HEAD de `image_url` antes de crear contenedor Instagram | Fallos de accesibilidad pública |
| **Circuit breaker** | Si 3 fallos consecutivos en una red → pausar 24h + alerta | Sanciones por spam / blacklisting |
| **needs_review flag** | Si `content_type=workshop/manual` o marcado explícitamente → cola de aprobación | Contenido sensible sin revisión |

### Schedules recomendados

| Red | Hora(s) de publicación | Prioridad |
|-----|----------------------|-----------|
| X | 08:30, 12:00, 17:00 (CET) | news > posts |
| LinkedIn | 08:30, 12:00 (CET, días laborables) | posts > news |
| Instagram | 09:00, 18:00 (CET) | posts con imagen primero |
| Facebook | 10:00, 19:00 (CET) | news + posts |

---

## Gestión de secretos (Key Vault `kv-azrbrnsblog`)

| Secreto | Descripción | Rotación |
|---------|-------------|----------|
| `rrss-x-access-token` | X OAuth 2.0 access token | Automática con refresh token |
| `rrss-x-refresh-token` | X OAuth 2.0 refresh token | Manual cada 6 meses |
| `rrss-x-api-key` | X API consumer key | Manual |
| `rrss-x-api-secret` | X API consumer secret | Manual |
| `rrss-linkedin-access-token` | LinkedIn access token (60 días) | Automática con refresh |
| `rrss-linkedin-client-id` | LinkedIn app client ID | Manual |
| `rrss-linkedin-client-secret` | LinkedIn app client secret | Manual |
| `rrss-meta-access-token` | Meta long-lived access token (60 días) | Automática con refresh |
| `rrss-meta-page-id` | Facebook Page ID | Manual |
| `rrss-meta-ig-user-id` | Instagram User ID | Manual |
| `rrss-publisher-token` | Token HMAC para autenticar el publisher endpoint | Manual cada 90 días |

---

## Infraestructura como código

Los recursos nuevos se despliegan mediante Bicep referenciando los RGs existentes:

```
azurebrains-rrss/bicep/
├── main.bicep                  ← Orquestador: storage + Cosmos collections + RBAC
├── modules/
│   ├── blob-storage.bicep      ← stazrbrnsmedia con container rrss-media público
│   └── cosmos-rrss.bicep       ← Contenedores rrss en Cosmos existente
└── parameters/
    └── prod.json               ← Parámetros de producción
```

> Los recursos de Azure OpenAI, AI Search y Key Vault son **existentes** — no se reproducen en este Bicep. Solo se añaden RBAC assignments nuevos (MI → Blob Data Contributor, MI → Cosmos Data Contributor).

---

## Estimación de costes

### Infraestructura nueva (sólo incremento sobre lo existente)

| Recurso | Coste estimado/mes | Notas |
|---------|-------------------|-------|
| Azure Blob Storage (stazrbrnsmedia) | ~$1-2 | ≈500 imágenes × 500KB = 250MB. LRS Standard. |
| Cosmos DB (nueva colección rrss) | ~$0 | Inside throughput existente del Cosmos (serverless) |
| Azure Functions / Container (publisher) | ~$0-5 | Consumption plan + ~720 invocaciones/mes. Free tier cubre ampliamente. |
| **Total infraestructura nueva** | **~$3-7/mes** | Coste marginal sobre infraestructura ya pagada |

### Coste de APIs de RRSS

| API | Modelo de coste | Estimación |
|-----|----------------|------------|
| X API v2 | Pay-per-usage (créditos), precios en consola | Monitorear en Developer Console |
| LinkedIn API | Gratuita para volúmenes orgánicos | $0 para posting orgánico |
| Meta (Instagram/Facebook) | Gratuita para posting | $0 para posting orgánico |

### Coste de generación IA (incremento)

| Uso | Modelo | Estimación |
|-----|--------|------------|
| Copy por post (4 redes × 4 posts/día) | `gpt-4o-mini` | ~$1-2/mes |
| Imagen card por post | `dall-e-3` / `gpt-image-1` | ~$2-5/mes (2 imágenes por item × ~$0.04 por imagen) |
| **Total IA incremental** | | **~$3-7/mes** |

### **Coste total estimado: ~$6-14/mes** (sobre base existente)

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| App Review Meta bloquea go-live en Instagram/Facebook | Alta | Alto | MVP con cuentas de test (role users); preparar screencasts para Review; Business Verification en paralelo |
| URL pública de imagen rechazada por Instagram | Media | Alto | Validación preflight; MIME correcto; blob storage público con URL directa sin redirecciones |
| Token X expirado / rate limit | Media | Medio | Refresh automático; headers `x-rate-limit-*`; backoff con jitter |
| Copy con patrones repetitivos → flag spam en X/Meta | Baja | Alto | Variación por red; deduplicación semántica; circuit breaker |
| Cambio de versión API LinkedIn (header `Linkedin-Version`) | Media | Medio | Monitoreo de changelog de LinkedIn; encapsulación del conector; variable configurable |
| Re-publicación por re-ejecución del pipeline | Baja | Alto | Idempotencia strong por `idempotency_key` en Cosmos (ya contemplada) |

---

## Checklist de pruebas (pre-producción)

### Idempotencia
- [ ] Ejecutar el mismo `content_item` 3 veces → sólo 1 publicación
- [ ] Simular retry tras fallo en red → reintentos dentro de límites

### Controles anti-spam
- [ ] Publicar 5 items con copy similar → verificar variación generada es >30% diferente
- [ ] Verificar que `fingerprint` evita duplicados exactos

### Media
- [ ] Instagram: imagen en blob storage accesible públicamente (cURL desde internet)
- [ ] Instagram: ratio dentro de 4:5 a 1.91:1; tamaño ≤8 MB
- [ ] X: imagen ≤5 MB; formato JPG/PNG/WEBP

### Rate limits / errores
- [ ] Token expirado → degradar a `needs_attention` sin reintentos infinitos
- [ ] Simular 429 → backoff y reintento correcto

### E2E
- [ ] Post nuevo en blog → manifest.json actualizado → announce.yml disparado → delivery_job creado → publicado en X con link correcto
- [ ] Verificar that `remote_post_id` queda registrado en Cosmos

---

## Próximos pasos

1. **Revisar este PLAN.md** y validar que los recursos Azure propuestos son los correctos
2. **Iniciar FASE 0**: registrar aplicaciones en X, LinkedIn y Meta (puede tomar 1-2 semanas por App Review de Meta)
3. **Implementar FASE 1** en paralelo: manifest del blog no depende de accesos a redes
4. **MVP Go/No-Go**: evaluar cuando FASE 1 + X + LinkedIn estén completos (Instagram/Facebook sujeto a App Review)
5. Si se aprueba: implementar FASE 2 y FASE 3 iterativamente por plataforma
