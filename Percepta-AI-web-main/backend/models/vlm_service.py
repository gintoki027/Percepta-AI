"""
Pluggable VLM (Vision-Language Model) service for scene summarization.
Supports: Hugging Face Inference API (OpenAI-compatible), Ollama.
"""

import base64
import io
import httpx
from PIL import Image
import config


class VLMService:
    """Abstract VLM interface."""

    async def describe_scene(self, image_bytes: bytes) -> str:
        raise NotImplementedError


class HuggingFaceVLM(VLMService):
    """
    Calls Hugging Face Inference API using the OpenAI-compatible
    chat completions endpoint for vision-language models.
    """

    def __init__(self):
        # Unified chat completions endpoint (model specified in payload)
        self.api_url = "https://router.huggingface.co/v1/chat/completions"
        self.model_id = config.HF_MODEL_ID
        self.headers = {
            "Content-Type": "application/json"
        }
        token = config.HF_API_TOKEN.strip() if config.HF_API_TOKEN else ""
        if token and token != "your_hf_token_here":
            self.headers["Authorization"] = f"Bearer {token}"
            print(f"[VLM] HF token configured: {token[:8]}...")
        else:
            print("[VLM] WARNING: No valid HF_API_TOKEN set! Scene description will fail.")
        self.last_error = None  # Track last error to avoid repeating
        print(f"[VLM] Using Hugging Face: {self.model_id}")
        print(f"[VLM] Endpoint: {self.api_url}")

    async def describe_scene(self, image_bytes: bytes) -> str:
        """Send image to HF API and get scene description."""
        try:
            img_b64 = base64.b64encode(image_bytes).decode("utf-8")

            # Detect image format
            if image_bytes[:3] == b'\xff\xd8\xff':
                mime = "image/jpeg"
            elif image_bytes[:4] == b'\x89PNG':
                mime = "image/png"
            else:
                mime = "image/jpeg"

            data_uri = f"data:{mime};base64,{img_b64}"

            # OpenAI-compatible chat completions format for VLMs
            payload = {
                "model": self.model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": data_uri}
                            },
                            {
                                "type": "text",
                                "text": config.VLM_PROMPT
                            }
                        ]
                    }
                ],
                "max_tokens": 100,
                "stream": False
            }

            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=self.headers
                )

                if response.status_code == 200:
                    self.last_error = None
                    result = response.json()
                    choices = result.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        if content:
                            return content.strip()
                    return ""

                elif response.status_code == 503:
                    # Model loading — log once, return empty (don't speak errors)
                    if self.last_error != 503:
                        print("[VLM] Model is loading. Will retry automatically.")
                        self.last_error = 503
                    return ""
                else:
                    if self.last_error != response.status_code:
                        print(f"[VLM] HF API error {response.status_code}: {response.text}")
                        self.last_error = response.status_code
                    return ""

        except httpx.TimeoutException:
            if self.last_error != "timeout":
                print("[VLM] Request timed out.")
                self.last_error = "timeout"
            return ""
        except Exception as e:
            if self.last_error != str(e):
                print(f"[VLM] Error: {e}")
                self.last_error = str(e)
            return ""


class OllamaVLM(VLMService):
    """
    Calls local Ollama instance for Qwen2-VL.
    Requires Ollama running with qwen2-vl model pulled.
    """

    def __init__(self):
        self.base_url = config.OLLAMA_BASE_URL
        self.model = config.OLLAMA_MODEL
        print(f"[VLM] Using Ollama: {self.model} at {self.base_url}")

    async def describe_scene(self, image_bytes: bytes) -> str:
        """Send image to Ollama and get scene description."""
        try:
            img_b64 = base64.b64encode(image_bytes).decode("utf-8")

            payload = {
                "model": self.model,
                "prompt": config.VLM_PROMPT,
                "images": [img_b64],
                "stream": False,
                "options": {
                    "num_predict": 80
                }
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "Unable to describe scene.")
                else:
                    return f"Ollama error: {response.status_code}"

        except httpx.ConnectError:
            return "Cannot connect to Ollama. Is it running?"
        except Exception as e:
            return f"VLM error: {str(e)}"


class DummyVLM(VLMService):
    """Fallback when no VLM is configured."""

    async def describe_scene(self, image_bytes: bytes) -> str:
        return "Scene description not configured. Set VLM_PROVIDER in .env"


def create_vlm_service() -> VLMService:
    """Factory: create the appropriate VLM service based on config."""
    provider = config.VLM_PROVIDER.lower()

    if provider == "huggingface":
        return HuggingFaceVLM()
    elif provider == "ollama":
        return OllamaVLM()
    else:
        print("[VLM] No VLM provider configured. Scene descriptions disabled.")
        return DummyVLM()
