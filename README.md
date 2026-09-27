# Multi-Tenant Wallet API

A small wallet/ledger service built with Django + Django REST Framework.
Multiple tenants (merchants/organizations) share the platform; each
tenant's users, wallets, and transactions are fully isolated from the
others.

## Setup

```bash
git clone https://github.com/nomanstine/wallet-api
cd wallet-api
cp .env.example .env
docker compose up --build -d
```

This starts Postgres and the Django dev server on `http://localhost:8000`

Running the tests
```bash
docker compose exec web python manage.py test
```


## Design overview

**Data model**

- `Tenant` — a merchant/organization. Has a generated `api_key`.
- `TenantUser` — a user/customer belonging to a tenant.
- `Wallet` — belongs to a tenant and a user. Holds a **cached** `balance`
  (`DecimalField`, never a float).
- `Transaction` — one immutable ledger row per balance change
  (`DEPOSIT` / `WITHDRAWAL` / `TRANSFER_IN` / `TRANSFER_OUT`), including a
  `balance_after` snapshot. **The ledger is the source of truth** — `Wallet.balance`
  is only ever mutated in the same DB transaction, under a row lock, as the
  `Transaction` row that justifies the change. It could be dropped entirely
  and rebuilt by summing `Transaction` rows; it exists purely so a balance
  read doesn't have to do that.
- `Transfer` — links the two `Transaction` rows (debit + credit) that make
  up one transfer.
- `IdempotencyKey` — one row per `(tenant, key)`, storing the exact response
  (status + body) the first request produced, so retries replay it instead
  of re-running the operation.

**Multi-tenancy**

`TenantMiddleware` (`tenants/middleware.py`) resolves the tenant on every
request from an `X-Api-Key` header or
an `X-Tenant-ID` header, and sets `request.tenant`. Every queryset in every
view filters on `tenant=request.tenant`, so a wallet/user/transaction
belonging to another tenant simply doesn't exist as far as the query is
concerned — it 404s rather than 403s, so tenants can't even probe for the
existence of another tenant's data.

**Concurrency & atomicity**

`wallets/services.py` wraps each operation in `transaction.atomic()` and
locks the wallet row(s) with `select_for_update()` before reading the
balance. Transfers lock both wallets **in a stable sorted-by-id order**, so
two concurrent transfers going in opposite directions (A→B and B→A) can't
deadlock each other. This is exercised for real — not just asserted — by
`wallets/tests/test_concurrency.py`, which fires genuinely concurrent
requests from separate threads.

**Idempotency**

`wallets/idempotency.py` implements a Stripe-style idempotency-key flow:
the first request with a given `(tenant, key)` reserves that key inside the
same DB transaction as the operation (via a unique constraint), and caches
the resulting status + body — including a *business error* like insufficient
funds, so a retry after the balance changes doesn't silently succeed on a
request that originally should have failed. Reusing a key with different
parameters returns `409 idempotency_key_conflict`. A genuinely unexpected
exception is **not** cached (it re-raises and rolls the whole thing back)
so a real retry can happen.


## API reference

All endpoints except `POST /api/tenants/` require a tenant, resolved from
either header:

```
X-Api-Key: <tenant's api_key>
```
or
```
X-Tenant-ID: <tenant's id>
```

Amounts are decimal strings, e.g. `"10.00"`, never floats.

---

**Create a tenant** — the only unauthenticated endpoint; this is how a
tenant onboards. Returns `api_key` **once** — it isn't shown again on
later reads.

```
POST /api/tenants/
{"name": "Acme Corp"}

201
{"id": "...", "name": "Acme Corp", "api_key": "0vpDVB...", "created_at": "..."}
```

**Create a user under the tenant**

```
POST /api/users/          (requires tenant header)
{"name": "Alice", "email": "alice@example.com"}

201
{"id": "...", "name": "Alice", "email": "alice@example.com", "created_at": "..."}
```

**Create a wallet for that user**

```
POST /api/wallets/        (requires tenant header)
{"user_id": "<user id>", "currency": "USD"}

201
{"id": "...", "user": "<user id>", "currency": "USD", "balance": "0.00", "created_at": "..."}
```

**Deposit**

```
POST /api/wallets/<wallet_id>/deposit/
{"amount": "100.00", "idempotency_key": "dep-001", "description": "Initial top-up"}

201
{
  "wallet_id": "...",
  "balance": "100.00",
  "transaction": {
    "id": "...", "wallet_id": "...", "type": "DEPOSIT", "amount": "100.00",
    "balance_after": "100.00", "transfer_id": null,
    "description": "Initial top-up", "created_at": "..."
  }
}
```

Retrying the exact same request+key replays the same response and adds
the response header `Idempotent-Replayed: true` (`false` the first time).

**Withdraw** — same shape, `POST /api/wallets/<wallet_id>/withdraw/`.
Insufficient funds:

```
422
{"error": "insufficient_funds", "detail": "Wallet balance 100.00 is less than withdrawal amount 5000.00."}
```

**Transfer between two wallets of the same tenant**

```
POST /api/transfers/
{
  "from_wallet_id": "...", "to_wallet_id": "...",
  "amount": "30.00", "idempotency_key": "tr-001"
}

201
{
  "transfer_id": "...", "from_wallet_id": "...", "to_wallet_id": "...", "amount": "30.00",
  "out_transaction": {"...": "type: TRANSFER_OUT, balance_after: 70.00"},
  "in_transaction": {"...": "type: TRANSFER_IN, balance_after: 30.00"}
}
```

A `to_wallet_id`/`from_wallet_id` belonging to another tenant, or that
doesn't exist, returns `404`. Transferring a wallet to itself returns
`400 same_wallet_transfer`.

**Get balance**

```
GET /api/wallets/<wallet_id>/
200
{"id": "...", "user": "...", "balance": "70.00", "created_at": "..."}
```

**Paginated transaction history**

```
GET /api/wallets/<wallet_id>/transactions/
GET /api/wallets/<wallet_id>/transactions/?page=2
200
{"count": 2, "next": null, "previous": null, "results": [ {...}, {...} ]}
```

**Missing/invalid tenant credentials** → `401`:

```json
{"error": "tenant_resolution_failed", "detail": "Missing tenant credentials: provide X-Api-Key or X-Tenant-ID header."}
```

## Trade-offs & assumptions

- **DecimalField, not integer minor units.** The prompt allows either;
  `DecimalField(max_digits=14, decimal_places=2)` was simpler to make
  readable in this repo's time budget. Trade-off: it assumes exactly 2
  decimal places for every currency, which is wrong for e.g. JPY (0) or
  some crypto (8+). Integer minor units would be the better general
  solution.
- **Tenant creation is unauthenticated.** There's no "platform admin" auth
  layer in scope, so `POST /api/tenants/` is open — it's the only way to
  get an API key in the first place. In a real system this would sit
  behind its own platform-level auth.
- **API keys are stored in plaintext.** Called out in a code comment too —
  in production these should be hashed at rest like a password, and shown
  to the client exactly once.
- **One wallet = one (tenant, user, currency) combo**, and a user can hold
  multiple wallets (e.g. one per currency), rather than baking a 1:1
  user↔wallet assumption into the schema.
- **Idempotency key is a plain string, scoped to `(tenant, key)`** — not
  further scoped by endpoint/action, so reusing a key across a deposit and
  a withdraw is treated as a conflict (different `action` recorded), not
  two independent operations. I think this is the safer default for a
  client library to build against.
- **Idempotency caches error responses too** (e.g. `422 insufficient_funds`),
  not just successes. This matches how Stripe/most payment APIs define
  "idempotent": the same request always yields the same recorded outcome.
  The alternative (only cache success, let failures re-run) would let a
  network-retry after a legitimate rejection silently succeed later once
  the balance happens to change — that felt like the wrong default for
  money movement.
- **404 instead of 403 for cross-tenant access.** Chosen so a tenant can't
  distinguish "not yours" from "doesn't exist," which is the safer leak
  profile for a multi-tenant system.
- **No auth/permissions beyond tenant scoping** — there's no user-level
  login within a tenant (e.g. "can Alice see Bob's wallet within the same
  tenant?"). The prompt's isolation requirement is tenant-vs-tenant, so I
  didn't add a second permission layer for that.
- **Browsable API renderer left on** for convenience while testing by hand;
  trivial to remove for a stricter JSON-only API.
