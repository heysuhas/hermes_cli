"""Provider-Agnostic LLM Layer Abstraction.

Declares the base LLMProvider and concrete implementations for Ollama, InternalLLM, and OpenAI.
Allows switching models and inference providers via configuration changes.
"""

from __future__ import annotations

import abc
import os
from typing import Any, Generator, Dict, List, Optional


class LLMProvider(abc.ABC):
    """Abstract Base Class representing a provider-neutral LLM client interface."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.base_url = config.get("base_url", "")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "")

    @abc.abstractmethod
    def generate(self, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform a synchronous chat completion call.

        Args:
            messages: List of message dicts (role, content, etc.)
            options: Optional inference parameters (temperature, max_tokens, etc.)
        """
        pass

    @abc.abstractmethod
    def stream(self, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> Generator[Dict[str, Any], None, None]:
        """Perform a streaming chat completion call.

        Args:
            messages: List of message dicts (role, content, etc.)
            options: Optional inference parameters (temperature, max_tokens, etc.)
        """
        pass

    @abc.abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Return capabilities supported by this provider (e.g., tools, vision, reasoning)."""
        pass


class OllamaProvider(LLMProvider):
    """Local Ollama LLM provider implementation."""

    def __init__(self, config: Dict[str, Any]):
        # Default to local loopback URL if not provided
        config.setdefault("base_url", "http://127.0.0.1:11434/v1")
        super().__init__(name="ollama", config=config)

    def generate(self, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        import httpx
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            **(options or {})
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = httpx.post(url, json=payload, headers=headers, timeout=60.0)
        response.raise_for_status()
        return response.json()

    def stream(self, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> Generator[Dict[str, Any], None, None]:
        import httpx
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            **(options or {})
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with httpx.stream("POST", url, json=payload, headers=headers, timeout=60.0) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    import json
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "supports_tools": True,
            "supports_vision": True,
            "supports_reasoning": False,
            "local_execution": True
        }


class InternalLLMProvider(LLMProvider):
    """Enterprise Internal Private LLM provider implementation."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(name="internal_llm", config=config)

    def generate(self, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Connects to internal enterprise gateway endpoint
        import httpx
        url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            **(options or {})
        }
        headers = {
            "Content-Type": "application/json",
            "X-Enterprise-Client-ID": os.environ.get("ENTERPRISE_CLIENT_ID", "hermes-agent")
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = httpx.post(url, json=payload, headers=headers, timeout=60.0)
        response.raise_for_status()
        return response.json()

    def stream(self, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> Generator[Dict[str, Any], None, None]:
        import httpx
        url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            **(options or {})
        }
        headers = {
            "Content-Type": "application/json",
            "X-Enterprise-Client-ID": os.environ.get("ENTERPRISE_CLIENT_ID", "hermes-agent")
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with httpx.stream("POST", url, json=payload, headers=headers, timeout=60.0) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    import json
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

    def get_capabilities(self) -> Dict[str, Any]:
        # Enterprise gateway LLM supports custom routing, tools, and high security
        return {
            "supports_tools": True,
            "supports_vision": True,
            "supports_reasoning": True,
            "local_execution": False
        }


class OpenAIProvider(LLMProvider):
    """Standard OpenAI Chat Completions provider implementation."""

    def __init__(self, config: Dict[str, Any]):
        config.setdefault("base_url", "https://api.openai.com/v1")
        super().__init__(name="openai", config=config)

    def generate(self, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        import httpx
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            **(options or {})
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        response = httpx.post(url, json=payload, headers=headers, timeout=60.0)
        response.raise_for_status()
        return response.json()

    def stream(self, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> Generator[Dict[str, Any], None, None]:
        import httpx
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            **(options or {})
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        with httpx.stream("POST", url, json=payload, headers=headers, timeout=60.0) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    import json
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "supports_tools": True,
            "supports_vision": True,
            "supports_reasoning": True,
            "local_execution": False
        }


def create_llm_provider(provider_type: str, config: Dict[str, Any]) -> LLMProvider:
    """Factory function to build the appropriate LLMProvider client instance based on config."""
    prov_type = provider_type.lower().strip()
    if prov_type in ("ollama", "local_ollama"):
        return OllamaProvider(config)
    elif prov_type in ("internal_llm", "internal"):
        return InternalLLMProvider(config)
    elif prov_type in ("openai", "openai_compatible"):
        return OpenAIProvider(config)
    else:
        raise ValueError(f"Unknown LLM Provider type: {provider_type}. Initially support: Ollama, InternalLLM, OpenAI.")
