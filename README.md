# E-Commerce Order Tracker

## Overview
An e-commerce platform that manages orders, inventory, bookings, and payments in a centralized system. The core functionality enables viewing available items, managing pending orders, and tracking stock levels in real-time.

Initial scope is **API-only** — the FastAPI/Swagger UI serves as the interface during development. A frontend can be added later once the API is stable.

## Key Problems Solved
- **Order Management** - Track and manage customer orders through their full lifecycle
- **Structured Data Management** - Store and organize user credentials, order history, stock levels, and payment information
- **Payment Processing** - Accept and process customer payments asynchronously with retry support
- **Inventory Booking** - Temporarily reserve (decrement available) stock when a customer initiates checkout, releasing the reservation if payment fails or times out, and finalizing the deduction on successful payment
- **Stock Management** - Monitor and manage inventory levels in real-time

## Booking System Behavior (Important)
When a customer starts checkout:
1. Available stock is **decremented** immediately (reservation), making it unavailable to others
2. A reservation TTL is set (e.g., 15 minutes via Redis)
3. On successful payment: reservation is confirmed, stock deduction is permanent
4. On payment failure or TTL expiry: reservation is released, stock is restored

This prevents overselling. If stock is genuinely depleted, customers are informed and can join a waitlist or trigger a restock order.

## Tech Stack

### Backend (Python)
- **Framework**: FastAPI — lightweight, async, auto-generates OpenAPI docs
- **ORM**: SQLAlchemy (async mode with `asyncpg` driver)
- **Migrations**: Alembic — version-controlled schema changes from day one
- **Task Queue**: Celery — async payment processing, notification emails, reservation expiry
  - **Broker**: Redis (doubles as cache)
  - **Result Backend**: Redis
  - **Retry strategy**: Exponential backoff with dead-letter queue for failed tasks
- **Password Hashing**: bcrypt via `passlib`

### Database
- **Primary**: PostgreSQL (ACID compliance, JSON support, reliable at scale)
- **Caching / Broker / Session store**: Redis
  - Inventory reservation locks
  - Celery broker and result backend
  - JWT blocklist (for token revocation)

### Authentication & Security
- **Auth method**: JWT (JSON Web Tokens) via PyJWT
  - Access token: short-lived (15 min)
  - Refresh token: long-lived (7 days), stored server-side in Redis for revocation support
- **Password storage**: bcrypt hashing (never plaintext)
- **Rate limiting**: applied on all auth endpoints (login, register, password reset) to prevent brute force
- **Transport security**: HTTPS/TLS required in all non-local environments
- **Secrets management**: environment variables via `.env` (dev) and a secrets manager (e.g., AWS Secrets Manager or HashiCorp Vault) in production — never committed to version control
- **Input validation**: Pydantic models on all request bodies (FastAPI built-in)

### Frontend (Future Scope)
Not in initial scope. API-first design ensures any future frontend (React, Vue, React Native, Flutter) can integrate without backend changes.

### Payment Integration
- **Gateways**: Stripe (primary), PayPal or Razorpay as alternatives
- **Method**: Official Python SDKs
- **Handling**: Payments processed asynchronously via Celery; webhook endpoints for gateway callbacks
- **Failure handling**: Celery retry with exponential backoff; failed payments trigger reservation release

### Observability
- **Logging**: Structured JSON logging (compatible with log aggregators like Loki or CloudWatch)
- **Error tracking**: Sentry for exception capture and alerting
- **Metrics**: Prometheus-compatible metrics endpoint (via `prometheus-fastapi-instrumentator`)
- **Health checks**: `/health` and `/ready` endpoints for load balancer and container orchestration probes

### Additional Tools
- **API Documentation**: OpenAPI/Swagger (auto-generated with FastAPI)
- **Testing**: pytest + pytest-asyncio; integration tests hit a real test database (no mocking the DB layer)
- **Deployment**: Docker + Docker Compose (dev), extendable to Kubernetes for production
- **CI/CD**: GitHub Actions (lint, test, build, deploy pipeline)

## Core Features
- View available items with real-time stock levels
- Create and manage customer orders
- Reservation-based stock booking (prevents overselling)
- Async payment processing with failure recovery
- User authentication with token refresh and revocation
- Admin stock management

## Security Considerations

### Order Management
- All order endpoints require authentication — unauthenticated users cannot view or create orders
- Users may only read/modify their own orders; admin role required to access other users' orders (enforce at the API layer, not just the UI)
- Order state transitions (pending → paid → shipped → cancelled) must be validated server-side; clients cannot set arbitrary states
- Log all state transitions with user ID and timestamp for audit trail

### Structured Data Management
- Passwords are stored as bcrypt hashes — never logged, never returned in API responses
- Sensitive fields (card details, full payment info) are never stored locally — delegated entirely to the payment gateway
- Database credentials are injected via environment variables; never hardcoded or committed
- PostgreSQL user for the app should have least-privilege access (no `DROP`, no `TRUNCATE` in production)

### Payment Processing
- Never handle raw card data — use Stripe.js / gateway-hosted fields so card numbers never touch the server
- Validate all incoming webhook calls using the gateway's signature verification (e.g., `stripe.WebhookEvent.construct_from` with the signing secret)
- Idempotency keys on all payment requests to prevent duplicate charges on Celery retries
- Payment amounts are always calculated server-side — never trust a price sent from the client
- Failed payment events trigger immediate reservation release to restore stock

### Inventory Booking (DoS Prevention)
- **Per-user reservation cap**: maximum 3–5 active reservations at once — no legitimate user needs more
- **Rate limit checkout initiation**: e.g., 10 reservations/hour per account, 3/minute per IP
- **Account verification required**: email-verified accounts only; detect and reject disposable email domains
- **Payment method required before reservation**: tying a real payment method to the account deters throwaway attacks
- **Abandonment rate monitoring**: accounts with high reservation-to-payment abandonment ratios are flagged and rate-limited further or suspended
- **Stock spike alerting**: alert if >50% of any item's stock is reserved within a short window (e.g., 1 minute)
- **Short TTL**: keep reservation window at 10–15 minutes; shorter for high-demand items
- **Per-item user cap**: a single user cannot hold more than a set percentage of any item's total stock

### Stock Management
- Stock level updates (restock, manual adjustments) are admin-only endpoints
- All stock mutations go through atomic Redis operations + PostgreSQL transactions to prevent race conditions
- Stock cannot be decremented below zero — enforce at the DB level with a `CHECK (quantity >= 0)` constraint, not just application logic

### Authentication & JWT
- Access tokens expire in 15 minutes; refresh tokens in 7 days
- Refresh tokens are stored server-side in Redis — revocation is immediate (logout, password change, suspicious activity)
- Brute force protection: rate limit login, register, and password-reset endpoints; lock account after N consecutive failures
- Passwords must meet minimum complexity requirements (length, character classes)
- Password reset tokens are single-use, short-lived (15 min), and invalidated after use

### Transport & Infrastructure
- HTTPS/TLS enforced in all non-local environments; HTTP requests redirected to HTTPS
- CORS configured explicitly — do not use wildcard `*` in production
- Docker containers run as non-root users
- Secrets (DB credentials, JWT secret, Stripe keys) managed via `.env` locally and a secrets manager (AWS Secrets Manager / HashiCorp Vault) in production — `.env` is in `.gitignore`
- Dependency versions are pinned and regularly audited (`pip audit` in CI)

### Observability & Incident Response
- Never log sensitive data: passwords, tokens, card numbers, or full request bodies on auth endpoints
- Structured logs include user ID and request ID for traceability, but not PII beyond what is necessary
- Sentry alerts on unhandled exceptions; on-call runbook documented for payment and stock failures
- Health check endpoints (`/health`, `/ready`) do not expose internal system details in their responses

## Development Setup (Planned)
```bash
cp .env.example .env        # configure local secrets
docker compose up -d        # start PostgreSQL + Redis
alembic upgrade head        # apply migrations
uvicorn app.main:app --reload
```

## Next Steps (Ordered by Dependency)
- [ ] Define data models and database schema
- [ ] Set up Alembic and create initial migration
- [ ] Set up Docker + Docker Compose (dev environment)
- [ ] Implement user authentication (registration, login, JWT refresh, rate limiting)
- [ ] Set up core API endpoints (items, orders)
- [ ] Design and implement booking/reservation system
- [ ] Celery setup: broker, workers, retry config
- [ ] Payment gateway integration (Stripe first)
- [ ] Add structured logging, Sentry, and health check endpoints
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Write integration test suite

