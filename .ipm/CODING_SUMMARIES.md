# Coding Summaries

Established patterns and style decisions captured from implementation tasks. Use this as knowledge for future planning and implementation sessions.

---

## Service-Layer Authorization

### Ownership Validation at Service Layer (Defense-in-Depth)

**Context:** Round 3, Task 1 — Add ownership validation to `WorkspaceService.delete_workspace`

Service methods that perform destructive operations should validate authorization themselves, not rely solely on API-layer checks. This prevents accidental misuse if the service is called from a management command or future endpoint.

**Pattern:** After fetching the target resource, verify the caller's membership and role before proceeding:

```python
membership = WorkspaceMember.objects.filter(user=user, workspace=workspace).select_for_update().first()
if not membership or membership.role != Role.OWNER:
    raise WorkspacePermissionDeniedError()
```

**Exception pattern:** New exception inherits from `PermissionDeniedError` (403) with `default_message` and `default_code`:
```python
class WorkspacePermissionDeniedError(PermissionDeniedError):
    default_message = 'Only the workspace owner can perform this action.'
    default_code = 'workspace_permission_denied'
```

**Files changed:** `backend/workspaces/exceptions.py`, `backend/workspaces/services.py`, `backend/workspaces/tests/test_services.py`

---

## Data Hierarchy & Cascade Behavior

### Orphaned Records on Deletion with `on_delete=SET_NULL`

**Context:** Task 1 — BudgetAccount deletion cleanup

`Transaction`, `PlannedTransaction`, and `CurrencyExchange` all have `on_delete=models.SET_NULL` on their `budget_period` ForeignKey. This means Django will **not** cascade-delete them when a parent is deleted — instead it sets `budget_period=NULL`, leaving orphaned rows. These orphans still hold FK references to `Currency` (with `on_delete=PROTECT`), which can block downstream deletions (Currency, Workspace) with unhandled 500 errors.

**Established pattern:** Any `delete()` method on a parent model that has `SET_NULL` children must explicitly delete those children first. This is already done in `BudgetPeriodService.delete()` and now also in `BudgetAccountService.delete()`.

The pattern:
```python
@staticmethod
@db_transaction.atomic
def delete(workspace_id: int, account_id: int) -> None:
    from currency_exchanges.models import CurrencyExchange
    from planned_transactions.models import PlannedTransaction
    from transactions.models import Transaction

    account = BudgetAccountService.get(account_id, workspace_id)
    period_ids = list(account.budget_periods.values_list('id', flat=True))
    Transaction.objects.filter(budget_period_id__in=period_ids).delete()
    PlannedTransaction.objects.filter(budget_period_id__in=period_ids).delete()
    CurrencyExchange.objects.filter(budget_period_id__in=period_ids).delete()
    account.delete()
```

**Key detail:** The reverse relation on `BudgetAccount` for periods is `budget_periods` (not `periods`). Always check the `related_name` in the model definition before using it.

**When adding new models:** If a new model has `on_delete=SET_NULL` on any FK, check whether parent deletion services need explicit cleanup. Also update `users/services.py:UserService.delete_account()` and `export_all_data()` per AGENTS.md GDPR rules.

---

## Testing Patterns

### Factory Usage for Financial Records

The factories for financial records (`TransactionFactory`, `PlannedTransactionFactory`, `CurrencyExchangeFactory`) default to creating their own `BudgetPeriod` and `User` via `SubFactory`. When tests need records tied to a specific workspace/account/period, pass these explicitly:

```python
period = BudgetPeriodFactory(
    budget_account=account,
    start_date='2025-01-01',
    end_date='2025-01-31',
    created_by=self.user,
)
pln = self.workspace.currencies.get(symbol='PLN')
transaction = TransactionFactory(
    budget_period=period,
    currency=pln,
    created_by=self.user,
    updated_by=self.user,
)
```

### Stale Test DB Issues

If tests fail with `NotNullViolation` on fields that exist in the DB but not in code (e.g., `email_verified`), it's likely a stale test DB from a different branch. Use `--create-db` to rebuild:

```bash
pytest --create-db -v
```

This is safe to use whenever cross-branch migrations cause schema drift.

### Test Class Structure

Tests use `AuthMixin` + `APIClientMixin` with `TestCase`. The `AuthMixin` creates a workspace with PLN+USD currencies (via `WorkspaceFactory`), a user, a workspace membership, and a default "General" `BudgetAccount`. The mixin also creates an `auth_token` and provides `auth_headers()`.

Custom helpers on the test class (e.g., `create_budget_account`) should use `self.workspace`, `self.user` from the mixin.

---

## Model Relationships Quick Reference

| Parent | Child | FK Field | on_delete | related_name |
|--------|-------|----------|-----------|-------------|
| BudgetAccount | BudgetPeriod | `budget_account` | CASCADE | `budget_periods` |
| BudgetPeriod | Transaction | `budget_period` | SET_NULL | `transactions` |
| BudgetPeriod | PlannedTransaction | `budget_period` | SET_NULL | `planned_transactions` |
| BudgetPeriod | CurrencyExchange | `budget_period` | SET_NULL | `currency_exchanges` |
| Workspace | BudgetAccount | `workspace` | CASCADE | (default) |
| Workspace | Currency | `workspace` | CASCADE | `currencies` |

---

## Build & Run Commands

```bash
# Backend
cd backend
uv run ruff check --fix . && uv run ruff format .   # Always after changes
uv run pytest <app>/tests/ -v --create-db            # Run tests (use --create-db when schema drift)

# Frontend
cd frontend
npm run lint                                          # Always after changes
```

---

## Token & Cache Patterns

### Single-Use Token Consumption via JTI + Django Cache

**Context:** Task 2 — Temp JWT single-use enforcement

Temp tokens (5-minute JWTs issued during 2FA login flow) must be single-use to prevent token replay attacks. This is enforced by:

1. Embedding a `jti` (JWT ID, a UUID) claim in each temp token via `create_temp_token()`
2. `consume_temp_token()` checks Django cache for that JTI — if found, the token was already used and returns `None`
3. On first use, the JTI is cached for 300s (matching token expiry)

The function lives in `common/auth.py` alongside `decode_temp_token` (the non-consuming variant, kept for cases where you need to peek without consuming).

**Pattern for token invalidation via cache:**
```python
cache_key = f'2fa_temp_token_used:{jti}'
if cache.get(cache_key):
    return None
cache.set(cache_key, True, 300)  # TTL matches token expiry
```

**Key detail:** `decode_temp_token` still exists as the non-consuming version. The only caller that needs consumption is `verify_2fa` in `core/api.py`, which uses `consume_temp_token`. If a new endpoint needs to inspect a temp token without consuming it, use `decode_temp_token`.

---

## Validate Stateful Dependencies Before Operations

### Reject Invisible Record Creation (No Matching Period)

**Context:** Task 3 — CurrencyExchange creation rejection when no period covers the date

`CurrencyExchangeService.create()` previously saved records with `budget_period_id=None` when no period covered the exchange date. These "orphan" records were invisible to the API (excluded by `for_workspace()` INNER JOIN) but persisted in the DB, causing data integrity issues.

**Established pattern:** When a service method depends on a resource being in a specific state (e.g., a period existing for a given date), validate that state **before** the main operation and raise a domain-specific exception. This prevents invisible/stale records and provides a meaningful error.

```python
period_id = CurrencyExchangeService._find_period_for_date(workspace_id, data.date)
if not period_id:
    raise CurrencyExchangeNoPeriodError()
```

After the guard, the `if period_id:` conditional wrapping balance updates is dead code and should be removed — balance updates always execute.

**Exception pattern:** New exception inherits from `ValidationError` with `default_message` and `default_code` class attributes:
```python
class CurrencyExchangeNoPeriodError(ValidationError):
    default_message = 'No budget period covers the given date. Create a period first.'
    default_code = 'currency_exchange_no_period'
```

**Endpoint response schema:** When a service can raise a `ValidationError`, the endpoint's `response` parameter must include `400: DetailOut`. Import `DetailOut` from `core.schemas.common`.

**Files changed:** `currency_exchanges/exceptions.py`, `currency_exchanges/services.py`, `currency_exchanges/api.py`, `currency_exchanges/tests/test_currency_exchanges.py`

---

## Frontend Error Handling

### Auth Response Guard — Missing `access_token`

**Context:** Task 4 — Handle missing `access_token` in auth responses

`login()`, `verify2FA()`, and `register()` in `AuthContext.tsx` previously did nothing when the backend returned a success response without an `access_token`. The user saw no feedback and was stuck.

**Established pattern:** Every auth function that expects an `access_token` in its response must have an `else` branch that shows a toast error when the token is missing:

```typescript
if (response.access_token) {
  // ... existing success logic
} else {
  toast.error('Unexpected response from server. Please try again.');
}
```

For `register()`, an early `return` is added after the toast to prevent proceeding with user setup (clearing query client, fetching user, navigating) when no token was received.

**Files changed:** `frontend/src/contexts/AuthContext.tsx`

---

## Frontend Component State Preservation

### CSS `hidden` vs Conditional Rendering for Stateful Components

**Context:** Task 5 — Preserve TwoFactorSection state on tab switch

When a component holds important transient state (e.g., recovery codes in `TwoFactorSection` with state machine `idle → setup → showing_codes`), conditional rendering (`{condition && <Component />}`) unmounts it on tab switch, permanently losing that state.

**Established pattern:** Use CSS `hidden` class to keep the component mounted but visually hidden:

```tsx
<div className={activeTab === 'security' ? '' : 'hidden'}>
  <TwoFactorSection />
</div>
```

This preserves internal React state (useState, useQuery caches, etc.) across tab switches. Only apply this pattern to components where state loss is problematic — other tabs can continue using conditional rendering.

**Files changed:** `frontend/src/pages/ProfilePage.tsx`

---

## Atomic Operations for Concurrent Safety

### Recovery Code Consumption with `select_for_update`

**Context:** Task 6 — Make recovery code consumption atomic

`TwoFactorService.verify_code()` previously performed two separate DB writes (recovery code removal and `last_used_at` update) without row locking. Under concurrent requests with the same recovery code, both could read the code before either wrote, allowing double-use.

**Established pattern:** For operations that must be atomic under concurrency:

1. Wrap the method in `@db_transaction.atomic`
2. Use `select_for_update()` on the queryset to acquire a row-level lock
3. Combine related field updates into a single `save()` call to minimize writes

```python
@staticmethod
@db_transaction.atomic
def verify_code(user: User, code: str) -> bool:
    """Verify a TOTP or recovery code. Uses select_for_update to prevent concurrent recovery code reuse."""
    try:
        twofa = UserTwoFactor.objects.select_for_update().get(user=user, is_enabled=True)
    except UserTwoFactor.DoesNotExist:
        return False
    ...
```

The helper function `_try_recovery_code` also includes `last_used_at` in its `save()` so that recovery code consumption and timestamp update happen in a single write while holding the lock.

**Files changed:** `backend/users/two_factor.py`

---

## API Schema Accuracy

### Document All Response Status Codes on Endpoints

**Context:** Task 7 — Add missing 404 to response schemas on 2FA management endpoints

Three 2FA endpoints in `users/api.py` could raise `NotFoundError` (404) through service-layer exceptions (e.g., `TwoFactorNotEnabledError` inherits from `NotFoundError`) but didn't declare 404 in their `response` parameter. This made the generated API schema inaccurate.

**Established pattern:** Every endpoint's `response` parameter must list **all** status codes the endpoint can return, including those from raised exceptions. This is documented in AGENTS.md but was missed on these 3 endpoints during initial implementation.

The three endpoints fixed:
- `verify_setup_2fa` — `response={200: TwoFAVerifySetupOut, 401: DetailOut, 404: DetailOut}`
- `disable_2fa` — `response={200: MessageOut, 401: DetailOut, 404: DetailOut}`
- `regenerate_2fa_codes` — `response={200: TwoFARegenerateOut, 401: DetailOut, 404: DetailOut}`

**Files changed:** `backend/users/api.py`

---

## Rate Limiting

### Per-Token Rate Limiting with Custom Key Extractor

**Context:** Task 8 — Add per-token rate limiting for verify-2fa

The existing `rate_limit` decorator in `common/throttle.py` keys only on client IP. An attacker with a stolen temp token could rotate IPs to get more 2FA verification attempts. The new `rate_limit_by_key` decorator accepts a `key_extractor` callable that derives an additional key component from the request (e.g., `user_id` from a temp token). The cache key becomes `ratelimit:{prefix}:{ip}:{key_part}`, so both IP and target user must change to bypass the limit.

```python
def rate_limit_by_key(key_prefix: str, key_extractor, limit: int = 10, period: int = 60):
    """Combines client IP with a custom key (e.g. user_id from temp token)."""
```

The key extractor for `verify-2fa` uses `decode_temp_token` (non-consuming) to peek at the token's `user_id`. Invalid tokens return `str(uuid.uuid4())` so each gets a unique bucket — a fixed key like `'invalid'` would let an attacker exhaust it from a shared IP, blocking legitimate 2FA for other users on that IP (see Round 3, Task 2).

### Rate Limit Values in Django Settings

All rate limit `limit` and `period` values are configured via Django settings, backed by env vars with sensible defaults. Each setting has an inline comment explaining its purpose and scope (per IP vs per IP+user):

```python
# Max 2FA verification attempts per IP+user within the period window
RATE_LIMIT_VERIFY_2FA = int(os.getenv('RATE_LIMIT_VERIFY_2FA', '10'))
# Time window (seconds) for 2FA verification rate limiting
RATE_LIMIT_VERIFY_2FA_PERIOD = int(os.getenv('RATE_LIMIT_VERIFY_2FA_PERIOD', '60'))
```

Endpoints reference these via `settings.RATE_LIMIT_*` instead of hardcoded values. This allows runtime configuration without code changes, and the comments serve as documentation for env var configuration.

**Files changed:** `backend/common/throttle.py`, `backend/core/api.py`, `backend/users/api.py`, `backend/config/settings.py`

### Unique Bucket per Invalid Token (No Shared Exhaustion)

**Context:** Round 3, Task 2 — Fix shared rate-limit bucket for invalid temp tokens

When `decode_temp_token` returns `None` (garbage/invalid token), the key extractor in `_extract_2fa_rate_key` returns `str(uuid.uuid4())` instead of a fixed string. This prevents all invalid-token attempts from sharing a single rate-limit bucket (`ratelimit:verify_2fa:{ip}:invalid`), which an attacker on a shared IP could exhaust to block legitimate 2FA verification for other users.

```python
def _extract_2fa_rate_key(request, data: Verify2FAIn = None, **kwargs):
    payload = decode_temp_token(data.temp_token)
    return str(payload.get('user_id', 'unknown')) if payload else str(uuid.uuid4())
```

The IP portion of the key still prevents unlimited flooding from a single source.

**Files changed:** `backend/core/api.py`
