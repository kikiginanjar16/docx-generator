# DOCX Contract Generator API

A production-oriented FastAPI service for generating `.docx` documents from structured JSON payloads and Word template files.  
The service supports template inspection, dynamic placeholder rendering, and optional AI-assisted clause generation for contract-style documents.

## Overview

This project is designed for teams that need a reliable document automation layer for:

- contract generation
- agreement drafting
- template-based business documents
- AI-assisted legal or administrative content composition

Core value proposition:

- **Template-first rendering** using `.docx` files and `{{ ... }}` placeholders
- **Flexible payload structure** driven entirely by your template schema
- **Optional AI augmentation** for selected document sections
- **Operationally simple** deployment via local runtime or Docker

## Key Capabilities

- Analyze template variables before rendering
- Generate documents from a remote template URL
- Generate documents from a direct template upload
- Inject AI-generated clauses into targeted fields via `ai_tasks`
- Auto-fill missing `ai.*` placeholders when `auto_ai_for_prefix=true`
- Stream the generated `.docx` file directly to the client

## Architecture

The service is intentionally small and layered:

```text
Client / Consumer
  |
  | HTTP JSON / multipart
  v
FastAPI Application (app/main.py)
  |
  |-- Request validation (Pydantic models)
  |-- Endpoint orchestration
  |-- Error handling / response streaming
  |
  +--> Template Retrieval / Parsing (app/docx.py)
  |     |-- Download template from URL
  |     |-- Read uploaded DOCX
  |     |-- Extract placeholders
  |     |-- Render final document
  |
  +--> AI Composition (app/ai.py)
  |     |-- Build OpenAI request
  |     |-- Generate clause text
  |
  +--> Context Utilities (app/utils.py)
        |-- Dot-path set/get
        |-- Prompt interpolation
        |-- Safe JSON excerpting
```

### Request Flow

For document generation, the runtime flow is:

1. Accept request payload and validate schema.
2. Load template from URL or uploaded file.
3. Build render context from `payload`.
4. Execute explicit `ai_tasks` if provided.
5. Optionally auto-generate missing `ai.*` fields.
6. Render the DOCX template with final context.
7. Return the generated file as a streamed download.

## Project Structure

```text
app/
  ai.py        OpenAI integration for clause generation
  docx.py      Template download, parsing, and rendering
  main.py      FastAPI app, routes, OpenAPI docs
  models.py    Request/response schemas
  utils.py     Context and interpolation helpers

sample.json        Example request payload
Dockerfile         Container image definition
docker-compose.yml Local container orchestration
requirements.txt   Python dependencies
```

## Quick Start

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Minimum expected configuration:

- set `OPENAI_API_KEY`
- optionally set `OPENAI_MODEL`
- optionally restrict `ALLOWED_TEMPLATE_HOSTS`

### 4. Run locally

```bash
uvicorn app.main:app --reload --port 8293
```

Documentation:

- Swagger UI: `http://localhost:8293/docs`
- Health check: `http://localhost:8293/healthz`

### 5. Run with Docker

```bash
docker compose up --build
```

## API Surface

### Health Check

`GET /healthz`

Returns:

```json
{
  "ok": true
}
```

### Analyze Template Variables

Use this when you want to inspect a template before generating a document.

`POST /template/analyze`

Request:

```json
{
  "template_url": "https://cdn.yourdomain.com/templates/pks_template.docx"
}
```

Response:

```json
{
  "variables": [
    "meta.number",
    "meta.date",
    "ai.pasal_ruang_lingkup"
  ]
}
```

Direct upload variant:

`POST /template/analyze-upload`

```bash
curl -X POST http://localhost:8293/template/analyze-upload \
  -F "template_file=@/path/to/template.docx"
```

Response example:

```json
{
  "variables": [
    "title",
    "ai.generated_intro"
  ],
  "suggested_request": {
    "payload": {
      "title": "Kiki"
    },
    "ai_tasks": [
      {
        "target_path": "ai.generated_intro",
        "prompt": "Buatkan satu paragraf singkat berbahasa Indonesia yang ramah dan profesional untuk menyapa {{ title }}. Maksimal 2 kalimat.",
        "max_chars": 4000
      }
    ],
    "auto_ai_for_prefix": false,
    "ai_prefix": "ai.",
    "output_filename": "template.docx",
    "temperature": 0.3
  }
}
```

For uploaded templates, the service now also attempts to generate a ready-to-use dummy request via OpenAI based on detected placeholders. If AI generation fails, a local fallback draft is returned.

### Generate DOCX

`POST /generate-docx`

This endpoint downloads the template from a URL and returns a streamed `.docx` file.

Example request:

```json
{
  "template_url": "https://cdn.yourdomain.com/templates/pks_template.docx",
  "output_filename": "PKS-Telkom-Miora.docx",
  "payload": {
    "meta": {
      "number": "001/PKS/II/2026",
      "date": "28 Februari 2026",
      "city": "Bandung"
    },
    "parties": {
      "pihak1": {
        "name": "PT Telkom Indonesia (Persero) Tbk",
        "address": "Jakarta"
      },
      "pihak2": {
        "name": "PT Miora Digital Nusantara",
        "address": "Bandung"
      }
    },
    "business": {
      "scope": "Pengembangan dan komersialisasi layanan digital",
      "term_months": 24,
      "revshare": "60%:40%"
    }
  },
  "ai_tasks": [
    {
      "target_path": "ai.pasal_ruang_lingkup",
      "prompt": "Buatkan PASAL RUANG LINGKUP untuk perjanjian kerja sama antara {{ parties.pihak1.name }} dan {{ parties.pihak2.name }}. Konteks: {{ business.scope }}. Format ayat (1)(2)(3), formal."
    },
    {
      "target_path": "ai.pasal_revenue_sharing",
      "prompt": "Buatkan PASAL SKEMA BAGI HASIL (revenue sharing) dengan pembagian {{ business.revshare }}. Sertakan definisi pendapatan, periode pelaporan, audit, pajak, dan mekanisme pembayaran."
    }
  ],
  "auto_ai_for_prefix": false,
  "temperature": 0.3
}
```

Example usage:

```bash
curl -X POST http://localhost:8293/generate-docx \
  -H "Content-Type: application/json" \
  -d @sample.json \
  --output out.docx
```

Direct upload variant:

`POST /generate-docx-upload`

Multipart fields:

- `template_file`: uploaded `.docx` template
- `request_json`: JSON string equivalent to the `generate-docx` body, excluding `template_url`

Example:

```bash
curl -X POST http://localhost:8293/generate-docx-upload \
  -F "template_file=@/path/to/template.docx" \
  -F 'request_json={
    "output_filename": "PKS-Telkom-Miora.docx",
    "payload": {
      "meta": { "number": "001/PKS/II/2026", "date": "28 Februari 2026", "city": "Bandung" },
      "parties": {
        "pihak1": { "name": "PT Telkom Indonesia (Persero) Tbk", "address": "Jakarta" },
        "pihak2": { "name": "PT Miora Digital Nusantara", "address": "Bandung" }
      }
    },
    "ai_tasks": [],
    "auto_ai_for_prefix": false,
    "temperature": 0.3
  }' \
  --output out.docx
```

## AI Generation Mode

There are two supported AI strategies:

- **Explicit mode**: provide `ai_tasks` to control exactly which fields are generated.
- **Automatic mode**: set `auto_ai_for_prefix=true` and allow the service to generate missing placeholders that start with `ai.`.

Automatic mode is useful when:

- the template already defines multiple `ai.*` placeholders
- you want less orchestration logic on the client side
- you accept a shared default prompting strategy

## DOCX Template Design Rules

Template quality directly affects rendering reliability.

Recommended placeholder patterns:

- `{{ meta.number }}`
- `{{ parties.pihak1.name }}`
- `{{ ai.pasal_ruang_lingkup }}`

Important constraints:

- Do not split one placeholder across multiple Word styles or text runs.
- Keep placeholder names stable and predictable.
- Prefer dot-path keys that map cleanly to JSON objects.

Bad practice example:

- half of `{{ meta.number }}` bold and the rest normal

That can cause Word to split the token internally and break template parsing.

## Operational Notes

- `ALLOWED_TEMPLATE_HOSTS=*` or an empty value allows any host.
- In production, use a strict allowlist to reduce SSRF risk.
- `TEMPLATE_MAX_MB` controls maximum accepted template size.
- `REQUEST_TIMEOUT_SEC` controls remote template download timeout.
- AI output is inserted as plain text; final visual formatting remains controlled by the Word template.

## Production Considerations

For a more robust deployment, consider:

1. Running behind a reverse proxy such as Nginx or an API gateway.
2. Restricting outbound template hosts with `ALLOWED_TEMPLATE_HOSTS`.
3. Storing templates in a controlled internal object store or CDN.
4. Adding request logging, tracing, and structured error monitoring.
5. Versioning templates and request contracts across clients.

## Developer Experience

The API exposes:

- a custom Swagger UI at `/docs`
- structured OpenAPI metadata
- a simple health endpoint for container/platform checks

This makes the service suitable for internal platform usage, partner integrations, or controlled business automation workflows.
