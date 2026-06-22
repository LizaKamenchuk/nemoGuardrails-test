from typing import Any


ORDERS: dict[str, dict[str, Any]] = {
    "12345": {
        "status": "In delivery",
        "can_return": True,
        "owner_user_id": "demo-user",
        "tenant_id": "demo-shop",
    },
    "77777": {
        "status": "Delivered",
        "can_return": False,
        "owner_user_id": "demo-user",
        "tenant_id": "demo-shop",
    },
    "99999": {
        "status": "Processing",
        "can_return": True,
        "owner_user_id": "another-user",
        "tenant_id": "demo-shop",
    },
}


def find_order(order_id: str) -> dict[str, Any] | None:
    return ORDERS.get(order_id)


def order_status(order_id: str) -> str:
    order = find_order(order_id)
    if not order:
        return "Order not found."
    return f"Order {order_id} status: {order['status']}."


def return_availability(order_id: str) -> str:
    order = find_order(order_id)
    if not order:
        return "Order not found."
    if order["can_return"]:
        return f"Order {order_id} can be returned."
    return f"Order {order_id} cannot be returned."
