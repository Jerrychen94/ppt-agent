"""模型提供方：mock（离线）与 OpenAI 兼容接口（DeepSeek / 通义 / OpenAI 等）。"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .errors import ProviderError


@dataclass
class Message:
    role: str
    content: str


class Provider:
    name = "base"

    def __init__(self) -> None:
        self.usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}

    def complete(self, messages: list[Message], *, temperature: float = 0.3, max_tokens: int = 4000) -> str:
        raise NotImplementedError


class MockProvider(Provider):
    """离线模式：内容由 mock.py 生成，这里不调用模型。"""

    name = "mock"

    def complete(self, messages: list[Message], *, temperature: float = 0.3, max_tokens: int = 4000) -> str:
        raise ProviderError(
            "MOCK_NO_LLM",
            "mock 模式不调用模型",
            "设置 PPT_PROVIDER=openai 与 PPT_API_KEY 后重试",
        )


class OpenAICompatProvider(Provider):
    name = "openai"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 120.0,
        retries: int = 2,
    ) -> None:
        super().__init__()
        if not api_key:
            raise ProviderError("MISSING_API_KEY", "缺少模型密钥", "设置 PPT_API_KEY 环境变量")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.retries = retries

    def complete(self, messages: list[Message], *, temperature: float = 0.3, max_tokens: int = 4000) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        url = f"{self.base_url}/chat/completions"
        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                content = payload["choices"][0]["message"]["content"]
                usage = payload.get("usage") or {}
                self.usage["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
                self.usage["completion_tokens"] += int(usage.get("completion_tokens") or 0)
                self.usage["calls"] += 1
                return content
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:300]
                last_error = ProviderError(f"HTTP_{exc.code}", f"模型接口返回 {exc.code}: {detail}", "检查密钥与模型名")
                if exc.code in (400, 401, 403, 404):
                    raise last_error
            except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
                last_error = ProviderError("UPSTREAM_ERROR", f"模型调用失败: {exc}", "检查网络与 base_url")
            if attempt < self.retries:
                time.sleep(1.5 * (attempt + 1))

        raise last_error or ProviderError("UPSTREAM_ERROR", "模型调用失败", "稍后重试")


def from_env(provider: str | None = None) -> Provider:
    chosen = (provider or os.getenv("PPT_PROVIDER") or ("openai" if os.getenv("PPT_API_KEY") else "mock")).lower()
    if chosen == "mock":
        return MockProvider()
    if chosen != "openai":
        raise ProviderError("INVALID_PROVIDER", f"不支持的 provider: {chosen}", "可选 mock / openai")
    return OpenAICompatProvider(
        base_url=os.getenv("PPT_BASE_URL", "https://api.deepseek.com/v1"),
        api_key=os.getenv("PPT_API_KEY", ""),
        model=os.getenv("PPT_MODEL", "deepseek-chat"),
        timeout=float(os.getenv("PPT_TIMEOUT", "120")),
        retries=int(os.getenv("PPT_RETRIES", "2")),
    )


def strip_fences(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json|markdown|md)?\s*(.*?)```", text, re.S)
    return match.group(1).strip() if match else text


def parse_json(text: str) -> dict:
    cleaned = strip_fences(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ProviderError("INVALID_JSON", "模型输出不是 JSON", "重试或降低温度") from None
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ProviderError("INVALID_JSON", f"模型输出不是 JSON: {exc}", "重试或降低温度") from exc
    if not isinstance(data, dict):
        raise ProviderError("INVALID_JSON", "模型输出顶层必须是对象", "要求返回 JSON 对象")
    return data
