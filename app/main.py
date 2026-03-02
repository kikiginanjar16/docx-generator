from __future__ import annotations
import importlib.util
import json
import logging
import os
import re
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from dotenv import load_dotenv
from pydantic import ValidationError

from .models import (
    GenerateDocxRequest,
    GenerateDocxUploadRequest,
    TemplateAnalyzeRequest,
    TemplateAnalyzeResponse,
)
from .docx import download_template, render_docx, extract_template_variables
from .utils import set_by_path, get_by_path, simple_interpolate, safe_json_excerpt
from .ai import generate_clause_text, generate_request_blueprint

load_dotenv()
logger = logging.getLogger("contract_gen_api")

_OPENAPI_TAGS = [
    {
        "name": "System",
        "description": "Operational endpoints for service health and runtime verification.",
    },
    {
        "name": "Template Analysis",
        "description": "Inspect DOCX templates and list Jinja-style placeholders before rendering.",
    },
    {
        "name": "Document Generation",
        "description": "Generate DOCX outputs from template sources, payload data, and optional AI tasks.",
    },
]

_SWAGGER_CUSTOM_CSS = """
body {
  background:
    radial-gradient(circle at top right, rgba(15, 118, 110, 0.16), transparent 32%),
    radial-gradient(circle at top left, rgba(30, 41, 59, 0.18), transparent 28%),
    linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
}
.swagger-ui {
  font-family: "SF Pro Text", "Segoe UI", ui-sans-serif, system-ui, sans-serif;
  color: #0f172a;
}
.swagger-ui .topbar {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #0f766e 100%);
  border-bottom: 1px solid rgba(148, 163, 184, 0.3);
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.16);
  padding: 12px 0;
}
.swagger-ui .topbar .download-url-wrapper {
  display: none;
}
.swagger-ui .topbar .link {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #f8fafc;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.swagger-ui .topbar .link::before {
  content: "DG";
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: linear-gradient(135deg, #14b8a6 0%, #0f766e 100%);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.25);
}
.swagger-ui .information-container.wrapper,
.swagger-ui .scheme-container,
.swagger-ui .wrapper {
  max-width: 1240px;
}
.swagger-ui .information-container {
  padding-top: 28px;
}
.swagger-ui .info {
  margin: 24px 0 12px;
}
.swagger-ui .info .title {
  color: #0f172a;
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.swagger-ui .info .title small {
  background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
  border-radius: 999px;
  color: #f8fafc;
  font-weight: 700;
}
.swagger-ui .scheme-container {
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 18px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
  margin: 0 0 24px;
  padding: 18px 24px;
}
.swagger-ui .opblock-tag {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 18px;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.06);
  margin: 0 0 14px;
  padding: 14px 18px;
}
.swagger-ui .opblock-tag:hover {
  background: #ffffff;
}
.swagger-ui .opblock {
  border-width: 1px;
  border-radius: 18px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
  margin: 0 0 18px;
  overflow: hidden;
}
.swagger-ui .opblock .opblock-summary {
  padding: 16px;
}
.swagger-ui .btn.authorize,
.swagger-ui .btn.execute {
  border-radius: 12px;
  font-weight: 700;
}
.swagger-ui .btn.execute {
  background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
  border-color: #0f766e;
  color: #f8fafc;
}
.swagger-ui .responses-inner,
.swagger-ui .opblock-section-header,
.swagger-ui .tab li button.tablinks,
.swagger-ui select,
.swagger-ui textarea,
.swagger-ui input[type=text] {
  border-radius: 12px;
}
.swagger-ui .model-box,
.swagger-ui section.models {
  background: rgba(255, 255, 255, 0.86);
  border-radius: 18px;
}
"""

app = FastAPI(
    title="DOCX Contract Generator API",
    summary="Document automation API for template analysis and DOCX generation.",
    description=(
        "A production-ready API for analyzing DOCX templates, generating richly structured "
        "documents from dynamic JSON payloads, and optionally composing clause text with AI."
    ),
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_tags=_OPENAPI_TAGS,
)
_HAS_MULTIPART = importlib.util.find_spec("multipart") is not None

def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        summary=app.summary,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    info = schema.setdefault("info", {})
    info["contact"] = {
        "name": "DOCX Generator Service",
    }
    info["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png",
        "altText": "DOCX Contract Generator",
    }
    schema["servers"] = [
        {"url": "/", "description": "Current environment"},
    ]
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = _custom_openapi

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

def _allowed_hosts() -> set[str]:
    raw = os.getenv("ALLOWED_TEMPLATE_HOSTS", "")
    return set([h.strip().lower() for h in raw.split(",") if h.strip()])

def _config():
    return {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "timeout": _env_int("REQUEST_TIMEOUT_SEC", 20),
        "max_mb": _env_int("TEMPLATE_MAX_MB", 10),
        "allowed_hosts": _allowed_hosts(),
    }

@app.get(
    "/docs",
    include_in_schema=False,
    response_class=HTMLResponse,
)
def custom_swagger_ui():
    html = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} | API Console",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "displayRequestDuration": True,
            "docExpansion": "list",
            "filter": True,
            "persistAuthorization": True,
            "syntaxHighlight.theme": "obsidian",
            "tryItOutEnabled": True,
        },
    )
    body = html.body.decode("utf-8")
    branded_body = body.replace("</head>", f"<style>{_SWAGGER_CUSTOM_CSS}</style></head>")
    branded_body = branded_body.replace(
        "Swagger UI",
        "DOCX Contract Generator",
        1,
    )
    response_headers = {
        key: value
        for key, value in html.headers.items()
        if key.lower() != "content-length"
    }
    return HTMLResponse(branded_body, status_code=html.status_code, headers=response_headers)

@app.get("/healthz", tags=["System"], summary="Health check")
def healthz():
    return {"ok": True}

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs for traceback."},
    )

async def _read_uploaded_template(file: UploadFile, *, max_mb: int) -> bytes:
    filename = (file.filename or "").lower()
    if not filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Uploaded template must be a .docx file")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded template is empty")
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Template too large (> {max_mb} MB)")
    return content

def _default_dummy_value(path: str):
    leaf = path.split(".")[-1].lower()
    if leaf in {"title", "name", "nama"}:
        return "Kiki"
    if "email" in leaf:
        return "kiki@example.com"
    if "phone" in leaf or "telp" in leaf or "hp" in leaf:
        return "081234567890"
    if "date" in leaf or "tanggal" in leaf:
        return "1 Maret 2026"
    if "city" in leaf or "kota" in leaf:
        return "Jakarta"
    if "address" in leaf or "alamat" in leaf:
        return "Jl. Contoh No. 1"
    if "number" in leaf or leaf in {"no", "nomor"}:
        return "001"
    if "company" in leaf or "perusahaan" in leaf:
        return "PT Contoh Indonesia"
    if "amount" in leaf or "harga" in leaf or "total" in leaf:
        return "1000000"
    return leaf.replace("_", " ").replace("-", " ").title() or "Contoh"

def _default_ai_prompt(target_path: str, payload_fields: list[str]) -> str:
    short_name = target_path.split(".", 1)[1] if "." in target_path else target_path
    short_lower = short_name.lower()
    ref = payload_fields[0] if payload_fields else None
    if ref and any(token in short_lower for token in ("intro", "greeting", "sapaan", "sambutan")):
        return (
            "Buatkan satu paragraf singkat berbahasa Indonesia yang ramah dan profesional "
            f"untuk menyapa {{{{ {ref} }}}}. Maksimal 2 kalimat."
        )

    references = payload_fields[:2]
    if references:
        context_text = ", ".join(f"{{{{ {item} }}}}" for item in references)
        return (
            f"Buatkan konten singkat berbahasa Indonesia yang profesional untuk bagian {short_name}. "
            f"Gunakan konteks {context_text} jika relevan. Maksimal 2 paragraf."
        )
    return (
        f"Buatkan konten singkat berbahasa Indonesia yang profesional untuk bagian {short_name}. "
        "Maksimal 2 paragraf."
    )

def _fallback_request_blueprint(*, variables: list[str], output_filename: str, temperature: float) -> GenerateDocxUploadRequest:
    payload_paths = [name for name in variables if not name.startswith("ai.")]
    ai_paths = [name for name in variables if name.startswith("ai.")]

    payload: dict = {}
    for path in payload_paths:
        set_by_path(payload, path, _default_dummy_value(path))

    ai_tasks = [
        {
            "target_path": path,
            "prompt": _default_ai_prompt(path, payload_paths),
            "max_chars": 4000,
        }
        for path in ai_paths
    ]

    return GenerateDocxUploadRequest(
        payload=payload,
        ai_tasks=ai_tasks,
        auto_ai_for_prefix=False,
        ai_prefix="ai.",
        output_filename=output_filename,
        temperature=temperature,
    )

def _suggested_output_filename(original_name: str | None) -> str:
    base_name = os.path.splitext(original_name or "")[0]
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", base_name).strip("-_").lower()
    stem = cleaned or "generated"
    return f"{stem}.docx"

def _build_suggested_request(*, variables: list[str], output_filename: str, cfg: dict) -> GenerateDocxUploadRequest:
    try:
        draft = generate_request_blueprint(
            model=cfg["model"],
            variables=variables,
            output_filename=output_filename,
            temperature=0.3,
        )
        return GenerateDocxUploadRequest.model_validate(draft)
    except Exception:
        return _fallback_request_blueprint(
            variables=variables,
            output_filename=output_filename,
            temperature=0.3,
        )

@app.post(
    "/template/analyze",
    response_model=TemplateAnalyzeResponse,
    tags=["Template Analysis"],
    summary="Analyze template from URL",
    description="Download a DOCX template from a URL and return all detected placeholders.",
)
def analyze_template(req: TemplateAnalyzeRequest):
    cfg = _config()
    try:
        tpl = download_template(str(req.template_url), timeout=cfg["timeout"], max_mb=cfg["max_mb"], allowed_hosts=cfg["allowed_hosts"])
        vars_ = sorted(extract_template_variables(tpl))
        return TemplateAnalyzeResponse(variables=vars_)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Analyze failed: {e}")

if _HAS_MULTIPART:
    @app.post(
        "/template/analyze-upload",
        response_model=TemplateAnalyzeResponse,
        tags=["Template Analysis"],
        summary="Analyze uploaded template",
        description="Upload a DOCX template directly and return all detected placeholders.",
    )
    async def analyze_template_upload(template_file: UploadFile = File(...)):
        cfg = _config()
        try:
            tpl = await _read_uploaded_template(template_file, max_mb=cfg["max_mb"])
            vars_ = sorted(extract_template_variables(tpl))
            suggested_request = _build_suggested_request(
                variables=vars_,
                output_filename=_suggested_output_filename(template_file.filename),
                cfg=cfg,
            )
            return TemplateAnalyzeResponse(variables=vars_, suggested_request=suggested_request)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Analyze failed: {e}")

def _default_auto_prompt(field: str, context: dict) -> str:
    # field is like "ai.pasal_ruang_lingkup"
    short_name = field.split(".", 1)[1] if "." in field else field
    excerpt = safe_json_excerpt(context, max_chars=2500)
    return (
        f"Buatkan konten untuk field: {short_name}.\n"
        "Gunakan bahasa Indonesia formal (dokumen perjanjian/kontrak).\n"
        "Jika cocok, tulis dalam format PASAL dan ayat (1)(2)(3).\n"
        "Konteks data (JSON ringkas):\n"
        f"{excerpt}\n"
        "Output: plain text saja."
    )

def _generate_docx_response(template_bytes: bytes, req, cfg: dict) -> StreamingResponse:
    # 1) context = payload (dynamic)
    context = dict(req.payload) if isinstance(req.payload, dict) else {}

    # 2) run explicit ai_tasks
    for task in req.ai_tasks:
        try:
            ai_prompt = simple_interpolate(task.prompt, context)
            text = generate_clause_text(model=cfg["model"], prompt=ai_prompt, temperature=req.temperature)
            if len(text) > task.max_chars:
                text = text[: task.max_chars].rstrip() + "\n[...dipotong karena max_chars...]"
            set_by_path(context, task.target_path, text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI task failed ({task.target_path}): {e}")

    # 3) optional: auto fill ai.* variables missing
    if req.auto_ai_for_prefix and req.ai_prefix:
        try:
            vars_ = extract_template_variables(template_bytes)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read template variables: {e}")

        ai_vars = [v for v in vars_ if v.startswith(req.ai_prefix)]
        for v in sorted(ai_vars):
            if get_by_path(context, v) is None:
                try:
                    prompt = _default_auto_prompt(v, context)
                    text = generate_clause_text(model=cfg["model"], prompt=prompt, temperature=req.temperature)
                    set_by_path(context, v, text)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Auto-AI failed ({v}): {e}")

    # 4) render docx
    try:
        out_bytes = render_docx(template_bytes, context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Render failed: {e}")

    filename = req.output_filename or "generated.docx"
    return StreamingResponse(
        iter([out_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@app.post(
    "/generate-docx",
    tags=["Document Generation"],
    summary="Generate DOCX from template URL",
    description="Render a DOCX document by downloading the template from a URL and applying the request payload.",
)
def generate_docx(req: GenerateDocxRequest):
    cfg = _config()

    # 1) download template
    try:
        tpl = download_template(str(req.template_url), timeout=cfg["timeout"], max_mb=cfg["max_mb"], allowed_hosts=cfg["allowed_hosts"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Template download failed: {e}")
    return _generate_docx_response(tpl, req, cfg)

if _HAS_MULTIPART:
    @app.post(
        "/generate-docx-upload",
        tags=["Document Generation"],
        summary="Generate DOCX from uploaded template",
        description="Upload a DOCX template file and render the generated document in a single request.",
    )
    async def generate_docx_upload(
        template_file: UploadFile = File(...),
        request_json: str = Form(...),
    ):
        cfg = _config()

        try:
            tpl = await _read_uploaded_template(template_file, max_mb=cfg["max_mb"])
        except HTTPException:
            raise

        try:
            req = GenerateDocxUploadRequest.model_validate_json(request_json)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=json.loads(e.json()))

        return _generate_docx_response(tpl, req, cfg)
