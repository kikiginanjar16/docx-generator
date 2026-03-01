from __future__ import annotations
import json
import os
import re
from typing import Any
from openai import OpenAI

_client: OpenAI | None = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

def generate_clause_text(*, model: str, prompt: str, temperature: float) -> str:
    """
    Generates clause text in Indonesian legal style.
    Uses the OpenAI Responses API via openai-python.
    """
    client = _get_client()
    resp = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "Kamu adalah legal drafter Indonesia. "
                    "Tulis formal, rapi, dan konsisten. "
                    "Jangan mengarang fakta; jika data kurang, gunakan placeholder [ ... ] yang jelas. "
                    "Hindari menyebut bahwa kamu AI."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )
    text = (resp.output_text or "").strip()
    return text

def generate_request_blueprint(*, model: str, variables: list[str], output_filename: str, temperature: float) -> dict[str, Any]:
    """
    Ask OpenAI to draft a JSON request body for the uploaded template.
    The model must return a single JSON object compatible with GenerateDocxUploadRequest.
    """
    client = _get_client()
    variable_list = "\n".join(f"- {name}" for name in variables) or "- (tidak ada variabel)"
    resp = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "Kamu menyusun request JSON untuk API DOCX generator. "
                    "Balas hanya dengan satu objek JSON valid tanpa markdown. "
                    "Tujuanmu adalah membuat data dummy yang realistis dan ringkas. "
                    "Variabel yang diawali 'ai.' jangan dimasukkan ke payload; buatkan item ai_tasks sebagai gantinya. "
                    "Set auto_ai_for_prefix ke false, ai_prefix ke 'ai.', pertahankan output_filename dan temperature yang diberikan. "
                    "Gunakan prompt AI berbahasa Indonesia, jelas, dan jika cocok referensikan payload memakai placeholder seperti {{ title }}."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Buatkan objek JSON dengan bentuk:\n"
                    "{\n"
                    '  "payload": {...},\n'
                    '  "ai_tasks": [{"target_path": "...", "prompt": "...", "max_chars": 4000}],\n'
                    '  "auto_ai_for_prefix": false,\n'
                    '  "ai_prefix": "ai.",\n'
                    f'  "output_filename": "{output_filename}",\n'
                    f'  "temperature": {temperature}\n'
                    "}\n\n"
                    "Daftar variabel template:\n"
                    f"{variable_list}\n\n"
                    "Aturan:\n"
                    "1. Semua variabel non-ai harus ada di payload dengan nilai dummy sesuai nama field.\n"
                    "2. Untuk setiap variabel ai.*, buat tepat satu ai_tasks.\n"
                    "3. Jika tidak ada variabel ai.*, ai_tasks harus array kosong.\n"
                    "4. Jangan tambahkan kunci di luar skema tersebut."
                ),
            },
        ],
        temperature=temperature,
    )
    text = (resp.output_text or "").strip()
    match = re.search(r"\{.*\}\s*$", text, re.DOTALL)
    raw_json = match.group(0) if match else text
    return json.loads(raw_json)
