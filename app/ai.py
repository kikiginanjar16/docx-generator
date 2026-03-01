from __future__ import annotations
import os
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
