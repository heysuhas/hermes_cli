"""NVIDIA NIM provider profile."""

from providers import register_provider
from providers.base import ProviderProfile

class NvidiaProviderProfile(ProviderProfile):
    def supports_tools_for_model(self, model: str | None) -> bool:
        # Gemma models on integrate.api.nvidia.com return 400 Bad Request
        # when tool calling is requested with streaming enabled.
        if model and "gemma" in model.lower():
            return False
        return self.supports_tools

nvidia = NvidiaProviderProfile(
    name="nvidia",
    aliases=("nvidia-nim",),
    env_vars=("NVIDIA_API_KEY",),
    display_name="NVIDIA NIM",
    description="NVIDIA NIM — accelerated inference",
    signup_url="https://build.nvidia.com/",
    fallback_models=(
        "nvidia/llama-3.1-nemotron-70b-instruct",
        "nvidia/llama-3.3-70b-instruct",
    ),
    base_url="https://integrate.api.nvidia.com/v1",
    default_max_tokens=16384,
    supports_tools=True,
)

register_provider(nvidia)
