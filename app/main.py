from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI

from app.schemas import ChatRequest, ChatResponse, MCPCallRequest, MCPCallResponse
from hub.agent import ShopAgent
from hub.audit import AuditLog
from hub.gateway import LLMGateway, NeMoRailsBackend
from hub.guardrails import DLPScanner, PlatformGuardrails, ShopAgentGuardrails
from hub.tools import MCPToolGateway, ToolContext


load_dotenv()

app = FastAPI(
    title="AI Hub Guardrails Demo",
    description=(
        "Shop agent demonstrating application rails, a shared LLM gateway, "
        "DLP checks, MCP tool authorization, and audit events."
    ),
)

audit_log = AuditLog()
tool_gateway = MCPToolGateway()


@lru_cache(maxsize=1)
def get_agent() -> ShopAgent:
    config_path = Path(__file__).resolve().parent.parent / "config"
    platform_guardrails = PlatformGuardrails(DLPScanner())
    llm_gateway = LLMGateway(
        backend=NeMoRailsBackend(config_path),
        guardrails=platform_guardrails,
        audit_log=audit_log,
    )
    return ShopAgent(
        agent_guardrails=ShopAgentGuardrails(),
        platform_guardrails=platform_guardrails,
        tools=tool_gateway,
        llm_gateway=llm_gateway,
        audit_log=audit_log,
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "components": [
            "agent-guardrails",
            "mcp-tool-gateway",
            "llm-gateway",
            "platform-guardrails",
            "dlp",
            "audit",
        ],
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    agent: ShopAgent = Depends(get_agent),
) -> ChatResponse:
    result = await agent.handle(
        message=request.message,
        user_id=request.user_id,
        tenant_id=request.tenant_id,
        request_id=request.request_id,
    )
    return ChatResponse(
        response=result.content,
        request_id=result.request_id,
        blocked=result.blocked,
        source=result.source,
    )


@app.get("/mcp/tools")
async def list_mcp_tools() -> dict[str, Any]:
    return {"tools": tool_gateway.list_tools()}


@app.post("/mcp/call", response_model=MCPCallResponse)
async def call_mcp_tool(request: MCPCallRequest) -> MCPCallResponse:
    result = await tool_gateway.call(
        request.tool_name,
        request.arguments,
        ToolContext(user_id=request.user_id, tenant_id=request.tenant_id),
    )
    return MCPCallResponse(
        content=result.content,
        allowed=result.allowed,
        reason=result.reason,
    )


@app.get("/debug/audit")
async def audit_events() -> dict[str, Any]:
    """Demo-only view; production audit access must require authorization."""

    return {"events": audit_log.list_events()}
