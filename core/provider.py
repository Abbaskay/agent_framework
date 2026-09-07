"""
core/provider.py — Provider-agnostic LLM layer.

The runner talks to this module, never to a vendor SDK. Each provider adapter
takes the framework's neutral message format, translates it to whatever its
vendor expects, and normalizes the reply back into a ProviderResponse.

The neutral format is OpenAI-shaped, because that is what the framework already
stored in Memory and what the majority of providers accept verbatim:

    {"role": "system"|"user"|"assistant"|"tool", "content": str,
     "tool_calls": [...], "tool_call_id": str}

Adding a provider = one class with a `complete()` method + one registry entry.
Keep adapters thin: translation only, no orchestration logic.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ToolCall:
    """A single tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict


@dataclass
class ProviderResponse:
    """Normalized LLM reply, identical in shape across every provider."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    # "stop" (model is done) | "tool_calls" (model wants tools) | anything else
    finish_reason: str = "stop"
    input_tokens: int = 0
    # The assistant turn re-serialized into neutral format, ready to append to
    # Memory. Providers must return something that can be sent back to them.
    assistant_message: dict = field(default_factory=dict)


class Provider(Protocol):
    """Interface every LLM backend must satisfy."""

    def complete(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        model: str,
        max_tokens: int,
    ) -> ProviderResponse:
        """Send one completion request and return a normalized response."""
        ...


class OpenAICompatibleProvider:
    """Adapter for any OpenAI-compatible chat completions endpoint.

    Covers DeepSeek and OpenAI itself — the only difference is base_url and
    which environment variable holds the key.
    """

    def __init__(self, api_key_env: str, base_url: str | None = None):
        self.api_key_env = api_key_env
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        """Construct the SDK client lazily so importing this module needs no key."""
        if self._client is None:
            from openai import OpenAI

            api_key = os.getenv(self.api_key_env)
            if not api_key:
                raise RuntimeError(
                    f"Missing API key: set {self.api_key_env} in your .env file."
                )
            kwargs = {"api_key": api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def complete(self, messages, system, tools, model, max_tokens) -> ProviderResponse:
        """Call the endpoint and normalize the reply."""
        client = self._get_client()

        full_messages = [{"role": "system", "content": system}] + messages
        kwargs = {
            "model": model,
            "messages": full_messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        assistant_message = {
            "role": "assistant",
            "content": message.content or "",
        }

        if message.tool_calls:
            # Re-serialize to plain dicts. The raw ChatCompletionMessage object
            # cannot be sent back to the API on the next turn.
            assistant_message["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    # A model can emit malformed JSON. Surface it as an empty
                    # call so the runner reports a tool error instead of crashing.
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        return ProviderResponse(
            text=message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            input_tokens=getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
            assistant_message=assistant_message,
        )


class AnthropicProvider:
    """Adapter for the Anthropic Messages API.

    Anthropic differs from the OpenAI shape in three ways, all handled here:
      - `system` is a top-level parameter, not a message
      - tool calls arrive as `tool_use` content blocks, not a `tool_calls` field
      - tool results go back as `tool_result` blocks inside a *user* turn
    """

    def __init__(self, api_key_env: str = "ANTHROPIC_API_KEY"):
        self.api_key_env = api_key_env
        self._client = None

    def _get_client(self):
        """Construct the SDK client lazily so importing this module needs no key."""
        if self._client is None:
            from anthropic import Anthropic

            api_key = os.getenv(self.api_key_env)
            if not api_key:
                raise RuntimeError(
                    f"Missing API key: set {self.api_key_env} in your .env file."
                )
            self._client = Anthropic(api_key=api_key)
        return self._client

    @staticmethod
    def _to_anthropic(messages: list[dict]) -> list[dict]:
        """Translate neutral (OpenAI-shaped) messages into Anthropic format."""
        converted: list[dict] = []
        for msg in messages:
            role = msg.get("role")

            if role == "tool":
                # Tool results ride inside a user turn as tool_result blocks.
                block = {
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": msg.get("content", ""),
                }
                # Merge into the previous user turn when possible, so parallel
                # tool calls produce one user message rather than several.
                if converted and converted[-1]["role"] == "user" and isinstance(
                    converted[-1]["content"], list
                ):
                    converted[-1]["content"].append(block)
                else:
                    converted.append({"role": "user", "content": [block]})

            elif role == "assistant" and msg.get("tool_calls"):
                blocks = []
                if msg.get("content"):
                    blocks.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    try:
                        args = json.loads(tc["function"]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": args,
                        }
                    )
                converted.append({"role": "assistant", "content": blocks})

            else:
                converted.append({"role": role, "content": msg.get("content", "")})

        return converted

    @staticmethod
    def _tools_to_anthropic(tools: list[dict]) -> list[dict]:
        """Flatten OpenAI function schemas into Anthropic's tool shape."""
        converted = []
        for tool in tools:
            fn = tool.get("function", tool)
            converted.append(
                {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "input_schema": fn.get(
                        "parameters", {"type": "object", "properties": {}}
                    ),
                }
            )
        return converted

    def complete(self, messages, system, tools, model, max_tokens) -> ProviderResponse:
        """Call the Messages API and normalize the reply back to neutral format."""
        client = self._get_client()

        kwargs = {
            "model": model,
            "system": system,
            "messages": self._to_anthropic(messages),
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = self._tools_to_anthropic(tools)

        response = client.messages.create(**kwargs)

        text_parts, tool_calls, openai_tool_calls = [], [], []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=block.input or {})
                )
                openai_tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input or {}),
                        },
                    }
                )

        text = "".join(text_parts)
        assistant_message = {"role": "assistant", "content": text}
        if openai_tool_calls:
            assistant_message["tool_calls"] = openai_tool_calls

        # Normalize Anthropic's stop_reason to the framework's vocabulary.
        finish_reason = "tool_calls" if tool_calls else "stop"

        return ProviderResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            input_tokens=getattr(response.usage, "input_tokens", 0) if response.usage else 0,
            assistant_message=assistant_message,
        )


# ---------------------------------------------------------------------------
# Provider registry — AgentConfig.provider is a key into this map.
# ---------------------------------------------------------------------------

PROVIDER_FACTORIES: dict[str, callable] = {
    "deepseek": lambda: OpenAICompatibleProvider(
        api_key_env="DEEPSEEK_API_KEY", base_url="https://api.deepseek.com"
    ),
    "openai": lambda: OpenAICompatibleProvider(api_key_env="OPENAI_API_KEY"),
    "anthropic": lambda: AnthropicProvider(),
}

# Providers are cached so one client is reused across an entire agent tree.
_PROVIDER_CACHE: dict[str, Provider] = {}


def get_provider(name: str) -> Provider:
    """Return the provider registered under `name`, constructing it once."""
    if name not in PROVIDER_FACTORIES:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {', '.join(PROVIDER_FACTORIES)}"
        )
    if name not in _PROVIDER_CACHE:
        _PROVIDER_CACHE[name] = PROVIDER_FACTORIES[name]()
    return _PROVIDER_CACHE[name]


def register_provider(name: str, factory: callable) -> None:
    """Register a custom provider factory. Used by tests to inject fakes."""
    PROVIDER_FACTORIES[name] = factory
    _PROVIDER_CACHE.pop(name, None)
