# Data Design

## Entities

```
User
Product
Order
OrderItem
Payment
Reservation
```

---

## User

```
id              UUID, primary key
email           unique, not null
password_hash   not null, never returned in responses
role            enum: customer | admin
is_verified     bool, default false
created_at      timestamp
```

**Decisions:**
- UUID over integer ID — harder to enumerate (`/users/1`, `/users/2`)
- `is_verified` gates reservation creation (email-verified accounts only)
- Role stored here, checked at the route level

---

## Product

```
id              UUID
name            not null
description     text
price           numeric(10,2)
stock_quantity  integer, CHECK >= 0
is_active       bool, default true
created_at      timestamp
updated_at      timestamp
```

**Decisions:**
- `numeric(10,2)` not `float` — floats have rounding errors, unacceptable for money
- `CHECK (stock_quantity >= 0)` at DB level — even if app logic fails, DB rejects negative stock
- `is_active` for soft deletes — products on historical orders must not be deleted

---

## Order

```
id              UUID
user_id         FK → users.id
status          enum: pending | reserved | paid | shipped | delivered | cancelled | refunded
total_amount    numeric(10,2)
created_at      timestamp
updated_at      timestamp
```

**Decisions:**
- `total_amount` snapshotted at creation — price changes don't affect existing orders
- Status transitions enforced by state machine, not the DB
- No address fields in initial scope

---

## OrderItem

```
id          UUID
order_id    FK → orders.id
product_id  FK → products.id
quantity    integer, CHECK > 0
unit_price  numeric(10,2)
```

**Decisions:**
- `unit_price` snapshotted from `product.price` at order time — this is why OrderItem exists as a separate table
- One order has many items (standard order/line-item pattern)

---

## Payment

```
id                  UUID
order_id            FK → orders.id, unique
stripe_payment_id   varchar, unique
amount              numeric(10,2)
status              enum: pending | processing | succeeded | failed | refunded
failure_reason      text, nullable
created_at          timestamp
updated_at          timestamp
```

**Decisions:**
- `stripe_payment_id` unique — idempotency, also used to verify webhooks
- `unique` on `order_id` — one payment record per order
- `failure_reason` stored for debugging and customer support

---

## Reservation

```
id          UUID
user_id     FK → users.id
product_id  FK → products.id
order_id    FK → orders.id, nullable
quantity    integer
expires_at  timestamp
is_active   bool, default true
created_at  timestamp
```

**Decisions:**
- Stored in both Redis (TTL for auto-expiry) and Postgres (audit trail, per-user cap enforcement)
- `expires_at` in Postgres lets you query active reservation counts per user reliably
- `order_id` is null at creation, set when payment succeeds
- Celery task watches for expired reservations and restores stock

---

## Relationships

```
User ──< Order ──< OrderItem >── Product
          │
          └──< Payment

User ──< Reservation >── Product
              │
              └── Order (nullable)
```

---

## DB-level Constraints

```sql
CHECK (products.stock_quantity >= 0)
CHECK (order_items.quantity > 0)
CHECK (reservations.quantity > 0)
UNIQUE (payments.order_id)
UNIQUE (payments.stripe_payment_id)
UNIQUE (users.email)
```

---

## Design Answers

| Question | Answer |
|---|---|
| Can a product go negative in stock? | No — DB constraint |
| Can prices change after an order? | Yes — doesn't affect orders, unit_price is snapshotted |
| Can a user have two payments for one order? | No — unique constraint |
| Can you audit what a user paid? | Yes — OrderItem.unit_price + Payment records |
| What happens if a reservation expires? | Celery task sets is_active=false, restores stock_quantity |
