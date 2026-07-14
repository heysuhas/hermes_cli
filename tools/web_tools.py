"""
web_tools.py - Web Tools Stub (Enterprise Governance)
"""
from typing import Any, Dict, List, Optional

def web_search_tool(query: str, limit: int = 5) -> str:
    raise NotImplementedError("Web search is disabled by enterprise security policy.")

async def web_extract_tool(urls: List[str], format: str = "markdown", use_llm_processing: bool = True) -> str:
    raise NotImplementedError("Web extraction is disabled by enterprise security policy.")

def check_web_api_key() -> bool:
    return False

def check_auxiliary_model() -> bool:
    return False
