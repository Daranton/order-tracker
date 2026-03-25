from enum import StrEnum


class OrderStatus(StrEnum):
    PENDING = "pending"
    RESERVED = "reserved"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class UserRole(StrEnum):
    CUSTOMER = "customer"
    ADMIN = "admin"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
