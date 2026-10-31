from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


class OllamaError(RuntimeError):
    pass


@dataclass(frozen=True)
class OllamaClient:
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5-coder-7b:latest"
    timeout_sec: float = 120.0

    @classmethod
    def from_environment(cls, *, model: str | None = None) -> "OllamaClient":
        return cls(
            base_url=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/"),
            model=model or os.environ.get("AFSIM_ASSISTANT_MODEL", "qwen2.5-coder-7b:latest"),
            timeout_sec=float(os.environ.get("AFSIM_OLLAMA_TIMEOUT_SEC", "120")),
        )

    def _request(self, path: str, payload: dict | None = None) -> dict:
        data = None
        headers = {"Accept": "application/json"}
        method = "GET"
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
            method = "POST"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OllamaError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OllamaError(f"cannot call Ollama at {self.base_url}: {exc}") from exc

    def health(self) -> dict:
        response = self._request("/api/tags")
        models = [item.get("name") for item in response.get("models", [])]
        return {
            "reachable": True,
            "base_url": self.base_url,
            "model": self.model,
            "model_available": self.model in models,
            "models": models,
        }

    def structured_chat(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
        num_ctx: int = 8192,
    ) -> dict:
        response = self._request(
            "/api/chat",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "format": schema,
                "options": {"temperature": 0, "num_ctx": int(num_ctx)},
            },
        )
        content = response.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama returned no structured message content")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise OllamaError(f"Ollama returned invalid JSON: {exc}") from exc

