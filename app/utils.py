from __future__ import annotations
from typing import Any, Dict
import re
import json

def set_by_path(obj: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur: Any = obj
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value

def get_by_path(obj: Dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    cur: Any = obj
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur

def simple_interpolate(template: str, data: Dict[str, Any]) -> str:
    """
    Very small interpolation: replaces {{ some.path }} with value from payload/context.
    Not full Jinja, but enough for AI prompts.
    """
    pattern = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")
    def repl(m: re.Match) -> str:
        key = m.group(1)
        val = get_by_path(data, key)
        return "" if val is None else str(val)
    return pattern.sub(repl, template)

def safe_json_excerpt(data: Dict[str, Any], max_chars: int = 3000) -> str:
    try:
        s = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        s = str(data)
    if len(s) > max_chars:
        return s[:max_chars] + "\n... (truncated) ..."
    return s
