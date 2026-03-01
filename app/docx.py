from __future__ import annotations
import io
from urllib.parse import urlparse
import requests
from docxtpl import DocxTemplate

def _host_allowed(url: str, allowed_hosts: set[str]) -> bool:
    if not allowed_hosts or "*" in allowed_hosts:
        return True
    host = urlparse(url).netloc.lower()
    return host in allowed_hosts

def download_template(url: str, *, timeout: int, max_mb: int, allowed_hosts: set[str]) -> bytes:
    if not _host_allowed(url, allowed_hosts):
        raise ValueError(f"Template host not allowed: {urlparse(url).netloc}")

    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    content = r.content

    if len(content) > max_mb * 1024 * 1024:
        raise ValueError(f"Template too large (> {max_mb} MB)")
    return content

def extract_template_variables(template_bytes: bytes) -> set[str]:
    buf = io.BytesIO(template_bytes)
    doc = DocxTemplate(buf)
    vars_ = doc.get_undeclared_template_variables()
    # docxtpl may return set already; normalize
    return set(vars_) if vars_ else set()

def render_docx(template_bytes: bytes, context: dict) -> bytes:
    tpl = io.BytesIO(template_bytes)
    doc = DocxTemplate(tpl)
    # If a key is missing, docxtpl typically raises. Keep it strict so users notice.
    doc.render(context)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
