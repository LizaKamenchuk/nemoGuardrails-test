from nemoguardrails.actions import action


ORDERS = {
    "12345": {
        "status": "In delivery",
        "can_return": True,
    },
    "77777": {
        "status": "Delivered",
        "can_return": False,
    },
}


@action()
async def get_order_status(order_id: str = "12345") -> str:
    order = ORDERS.get(order_id)
    if not order:
        return "Order not found."
    return f"Order {order_id} status: {order['status']}."


@action()
async def check_return_available(order_id: str = "12345") -> str:
    order = ORDERS.get(order_id)
    if not order:
        return "Order not found."
    if order["can_return"]:
        return f"Order {order_id} can be returned."
    return f"Order {order_id} cannot be returned."
