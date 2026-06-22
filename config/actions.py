from nemoguardrails.actions import action

from hub.orders import ORDERS, order_status, return_availability


@action()
async def get_order_status(order_id: str = "12345") -> str:
    return order_status(order_id)


@action()
async def check_return_available(order_id: str = "12345") -> str:
    return return_availability(order_id)
