from typing import Any, Dict, List
from pydantic import BaseModel, Field, HttpUrl

class AITask(BaseModel):
    """
    One AI job to fill one field.
    - target_path: where to store the AI output in the rendering context, e.g. "ai.pasal_ruang_lingkup"
    - prompt: instruction for AI. You can reference payload values using {{ dot.path }} interpolation.
    - max_chars: trims output if too long.
    """
    target_path: str = Field(..., examples=["ai.pasal_ruang_lingkup"])
    prompt: str
    max_chars: int = 4000

class TemplateAnalyzeRequest(BaseModel):
    template_url: HttpUrl

class GenerateDocxRequest(BaseModel):
    template_url: HttpUrl
    payload: Dict[str, Any]
    ai_tasks: List[AITask] = []
    # If true: auto-generate all template vars that start with "ai." when missing from payload/context.
    auto_ai_for_prefix: bool = False
    ai_prefix: str = "ai."
    output_filename: str = "generated.docx"
    temperature: float = 0.3

class GenerateDocxUploadRequest(BaseModel):
    payload: Dict[str, Any]
    ai_tasks: List[AITask] = []
    # If true: auto-generate all template vars that start with "ai." when missing from payload/context.
    auto_ai_for_prefix: bool = False
    ai_prefix: str = "ai."
    output_filename: str = "generated.docx"
    temperature: float = 0.3

class TemplateAnalyzeResponse(BaseModel):
    variables: List[str]
    suggested_request: GenerateDocxUploadRequest | None = None
