import re
from dataclasses import dataclass
from uuid import uuid4

from hub.audit import AuditLog
from hub.gateway import LLMGateway
from hub.guardrails import PlatformGuardrails, ShopAgentGuardrails
from hub.tools import MCPToolGateway, ToolContext


SHOP_REFUSAL = "I can help only with orders, delivery, payments, and returns."
SECURITY_REFUSAL = (
    "I cannot follow requests to ignore instructions, reveal hidden prompts, "
    "or process sensitive credentials."
)


@dataclass(frozen=True)
class AgentResult:
    content: str
    request_id: str
    blocked: bool
    source: str


class ShopAgent:
    """Application agent: business rails, tool routing, then shared LLM gateway."""

    _order_id = re.compile(r"\b(\d{5})\b")

    def __init__(
        self,
        *,
        agent_guardrails: ShopAgentGuardrails,
        platform_guardrails: PlatformGuardrails,
        tools: MCPToolGateway,
        llm_gateway: LLMGateway,
        audit_log: AuditLog,
    ) -> None:
        self._agent_guardrails = agent_guardrails
        self._platform_guardrails = platform_guardrails
        self._tools = tools
        self._llm_gateway = llm_gateway
        self._audit = audit_log

    async def handle(
        self,
        *,
        message: str,
        user_id: str,
        tenant_id: str,
        request_id: str | None = None,
    ) -> AgentResult:
        current_request_id = request_id or str(uuid4())

        security = self._platform_guardrails.inspect_input(message)
        if not security.allowed:
            self._record_agent_decision(current_request_id, False, security.reason)
            return AgentResult(SECURITY_REFUSAL, current_request_id, True, "agent-guardrails")

        topic = self._agent_guardrails.inspect(message)
        self._record_agent_decision(current_request_id, topic.allowed, topic.reason)
        if not topic.allowed:
            return AgentResult(SHOP_REFUSAL, current_request_id, True, "agent-guardrails")

        tool_name = self._select_tool(message)
        if tool_name:
            order_match = self._order_id.search(message)
            if not order_match:
                return AgentResult(
                    "Please provide a five-digit order id.",
                    current_request_id,
                    False,
                    "agent",
                )
            tool_result = await self._tools.call(
                tool_name,
                {"order_id": order_match.group(1)},
                ToolContext(user_id=user_id, tenant_id=tenant_id),
            )
            self._audit.record(
                request_id=current_request_id,
                stage="agent.tool_call",
                outcome="allow" if tool_result.allowed else "block",
                reason=tool_result.reason,
                tool_name=tool_name,
            )
            return AgentResult(
                tool_result.content,
                current_request_id,
                not tool_result.allowed,
                "mcp-tool-gateway",
            )

        gateway_result = await self._llm_gateway.complete(
            request_id=current_request_id,
            user_message=message,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        return AgentResult(
            gateway_result.content,
            current_request_id,
            gateway_result.blocked,
            "llm-gateway",
        )

    def _record_agent_decision(self, request_id: str, allowed: bool, reason: str) -> None:
        self._audit.record(
            request_id=request_id,
            stage="agent.input",
            outcome="allow" if allowed else "block",
            reason=reason,
        )

    @staticmethod
    def _select_tool(message: str) -> str | None:
        normalized = message.casefold()
        if any(term in normalized for term in ("return", "refund", "вернут", "возврат")):
            return "check_return_available"
        if "order" in normalized or "заказ" in normalized:
            return "get_order_status"
        return None
