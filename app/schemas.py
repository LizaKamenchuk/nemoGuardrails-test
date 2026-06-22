from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    user_id: str = "demo-user"
    tenant_id: str = "demo-shop"
    request_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    request_id: str
    blocked: bool
    source: str


class MCPCallRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    user_id: str = "demo-user"
    tenant_id: str = "demo-shop"


class MCPCallResponse(BaseModel):
    content: str
    allowed: bool
    reason: str
