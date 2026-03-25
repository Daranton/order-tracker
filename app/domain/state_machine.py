from app.domain.enums import OrderStatus

# Valid transitions: current status -> set of allowed next statuses
VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.RESERVED, OrderStatus.CANCELLED},
    OrderStatus.RESERVED: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.REFUNDED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: {OrderStatus.REFUNDED},
    OrderStatus.CANCELLED: set(),
    OrderStatus.REFUNDED: set(),
}


def can_transition(current: OrderStatus, next_status: OrderStatus) -> bool:
    return next_status in VALID_TRANSITIONS.get(current, set())


def transition(current: OrderStatus, next_status: OrderStatus) -> OrderStatus:
    if not can_transition(current, next_status):
        raise ValueError(f"Invalid transition: {current} -> {next_status}")
    return next_status
