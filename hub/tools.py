from dataclasses import dataclass
from typing import Any

from hub.orders import find_order, order_status, return_availability


@dataclass(frozen=True)
class ToolContext:
    user_id: str
    tenant_id: str


@dataclass(frozen=True)
class ToolResult:
    allowed: bool
    content: str
    reason: str


class MCPToolGateway:
    """MCP-shaped authorization boundary around business tools.

    The demo exposes this through HTTP. A production deployment can retain this
    policy class while replacing the transport with an MCP server implementation.
    """

    _tools = {
        "get_order_status": {
            "description": "Read the status of an order owned by the current user.",
            "required_arguments": ["order_id"],
            "read_only": True,
        },
        "check_return_available": {
            "description": "Check whether an owned order is eligible for return.",
            "required_arguments": ["order_id"],
            "read_only": True,
        },
    }

    def list_tools(self) -> dict[str, dict[str, Any]]:
        return self._tools

    async def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        if tool_name not in self._tools:
            return ToolResult(False, "Tool call blocked.", "tool_not_allowed")

        order_id = str(arguments.get("order_id", "")).strip()
        if not order_id.isdigit() or len(order_id) != 5:
            return ToolResult(False, "A valid five-digit order id is required.", "invalid_arguments")

        order = find_order(order_id)
        if not order:
            return ToolResult(True, "Order not found.", "order_not_found")
        if (
            order["owner_user_id"] != context.user_id
            or order["tenant_id"] != context.tenant_id
        ):
            return ToolResult(
                False,
                "Order not found or access denied.",
                "resource_access_denied",
            )

        if tool_name == "get_order_status":
            return ToolResult(True, order_status(order_id), "tool_completed")
        return ToolResult(True, return_availability(order_id), "tool_completed")
