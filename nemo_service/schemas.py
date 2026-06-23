from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GuardrailRequest(BaseModel):
    """LiteLLM Generic Guardrail API request subset used by this service."""

    model_config = ConfigDict(extra="allow")

    texts: list[str] = Field(default_factory=list)
    input_type: Literal["request", "response"]
    model: str | None = None
    structured_messages: list[dict[str, Any]] | None = None
    litellm_call_id: str | None = None
    litellm_trace_id: str | None = None


class GuardrailResponse(BaseModel):
    action: Literal["BLOCKED", "NONE", "GUARDRAIL_INTERVENED"]
    blocked_reason: str | None = None
    texts: list[str] | None = None
