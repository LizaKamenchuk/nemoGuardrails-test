from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from hub.audit import AuditLog
from hub.guardrails import PlatformGuardrails


PLATFORM_BLOCK_MESSAGE = (
    "The request was blocked by the shared AI platform security policy."
)
OUTPUT_BLOCK_MESSAGE = "The model response was blocked by the shared AI platform policy."


class ModelBackend(Protocol):
    async def generate(self, messages: list[dict[str, str]]) -> str: ...


class NeMoRailsBackend:
    """Lazy NeMo adapter so health checks and tool-only calls need no LLM key."""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._rails: Any = None

    def _get_rails(self) -> Any:
        if self._rails is None:
            from nemoguardrails import LLMRails, RailsConfig

            config = RailsConfig.from_path(str(self._config_path))
            self._rails = LLMRails(config)
        return self._rails

    async def generate(self, messages: list[dict[str, str]]) -> str:
        result = await self._get_rails().generate_async(messages=messages)
        if isinstance(result, dict):
            return str(result.get("content", ""))
        return str(result)


@dataclass(frozen=True)
class GatewayResult:
    content: str
    blocked: bool
    reason: str


class LLMGateway:
    """Shared LLM access gateway with platform-level pre/post rails."""

    def __init__(
        self,
        backend: ModelBackend,
        guardrails: PlatformGuardrails,
        audit_log: AuditLog,
    ) -> None:
        self._backend = backend
        self._guardrails = guardrails
        self._audit = audit_log

    async def complete(
        self,
        *,
        request_id: str,
        user_message: str,
        user_id: str,
        tenant_id: str,
    ) -> GatewayResult:
        pre = self._guardrails.inspect_input(user_message)
        self._audit.record(
            request_id=request_id,
            stage="gateway.pre_call",
            outcome="allow" if pre.allowed else "block",
            reason=pre.reason,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        if not pre.allowed:
            return GatewayResult(PLATFORM_BLOCK_MESSAGE, True, pre.reason)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a support assistant for an online shop. Answer only "
                    "about orders, delivery, payments, and returns."
                ),
            },
            {"role": "user", "content": user_message},
        ]
        try:
            response = await self._backend.generate(messages)
        except Exception:
            self._audit.record(
                request_id=request_id,
                stage="gateway.llm_call",
                outcome="error",
                reason="model_backend_error",
            )
            return GatewayResult("The AI service is temporarily unavailable.", True, "model_backend_error")

        self._audit.record(
            request_id=request_id,
            stage="gateway.llm_call",
            outcome="allow",
            reason="model_completed",
            estimated_characters=len(user_message) + len(response),
        )
        post = self._guardrails.inspect_output(response)
        self._audit.record(
            request_id=request_id,
            stage="gateway.post_call",
            outcome="allow" if post.allowed else "block",
            reason=post.reason,
        )
        if not post.allowed:
            return GatewayResult(OUTPUT_BLOCK_MESSAGE, True, post.reason)
        return GatewayResult(response, False, "completed")
