# AGENTS.md

Coding guidelines and commands for agentic coding agents working on the Monie codebase.

## Project Overview

Monie is a personal finance tracking application built with Django 6, Django Ninja, React 19, and PostgreSQL. It features multi-currency support, period-based budgeting, and collaborative team features.

## Build/Lint/Test Commands

### Backend (Django)

When running Python commands, always use the virtual environment:

```bash
backend/.venv/bin/python
```

```bash
cd backend

# Setup
uv venv && source .venv/bin/activate
uv sync
python manage.py migrate

# Development
python manage.py runserver

# Testing
pytest                                    # Run all tests
pytest -v                                 # Verbose output
pytest budget_accounts/tests/             # Run specific app tests
pytest budget_accounts/tests/test_api.py::TestClass::test_method  # Single test
pytest -k "test_create"                   # Run tests matching pattern
pytest --cov=. --cov-report=html          # With coverage
pytest --create-db -v                      # Fresh test DB (use when cross-branch migrations cause stale DB issues)

# Linting & Formatting
uv run ruff check .                       # Check linting issues
uv run ruff check --fix .                 # Auto-fix lint issues
uv run ruff format .                      # Format code
```

Always run `uv run ruff check` and `uv run ruff format` after making changes.

### Frontend (React + Vite)

```bash
cd frontend

# Setup
npm install

# Development
npm run dev                               # Runs at http://localhost:5173

# Build
npm run build                             # TypeScript check + Vite build

# Linting
npm run lint                              # ESLint check
```

Always run `npm run lint` after making changes.

## Data Hierarchy

All data operations follow this hierarchy:

```
Workspace → BudgetAccount → BudgetPeriod → [Category, Transaction, Budget, ...]
```

Every endpoint must verify resources belong to the user's workspace.

## Model Relationships Reference

| Parent | Child | FK Field | on_delete | related_name |
|--------|-------|----------|-----------|-------------|
| Workspace | BudgetAccount | `workspace` | CASCADE | (default) |
| Workspace | Currency | `workspace` | CASCADE | `currencies` |
| BudgetAccount | BudgetPeriod | `budget_account` | CASCADE | `budget_periods` |
| BudgetPeriod | Transaction | `budget_period` | SET_NULL | `transactions` |
| BudgetPeriod | PlannedTransaction | `budget_period` | SET_NULL | `planned_transactions` |
| BudgetPeriod | CurrencyExchange | `budget_period` | SET_NULL | `currency_exchanges` |

### SET_NULL Children Must Be Explicitly Deleted

`Transaction`, `PlannedTransaction`, and `CurrencyExchange` have `on_delete=SET_NULL` on their `budget_period` FK. Django does **not** cascade-delete them — it sets `budget_period=NULL`, leaving orphaned rows. These orphans hold FK references to `Currency` (with `on_delete=PROTECT`), which blocks downstream deletions with unhandled 500 errors.

Any `delete()` method on a parent model that has `SET_NULL` children must explicitly delete those children first:

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

> **When adding a new model with `on_delete=SET_NULL`**: Update every parent deletion service that could leave orphans. Also update `UserService.delete_account()` and `export_all_data()` per GDPR rules.

## Backend Code Style (Python)

### Imports

```python
# Standard library
from datetime import date
from decimal import Decimal

# Django/Django Ninja
from django.db import transaction as db_transaction
from django.http import HttpRequest
from ninja import Router

# Common utilities
from common.auth import WorkspaceJWTAuth
from common.exceptions import NotFoundError, ValidationError
from common.permissions import require_role

# Local apps (alphabetically)
from transactions.schemas import TransactionCreate, TransactionOut
from transactions.services import TransactionService
from workspaces.models import WRITE_ROLES
```

### Naming Conventions

- **Files**: snake_case (`transactions/api.py`, `period_balances/models.py`)
- **Classes**: PascalCase (`TransactionOut`, `BudgetPeriod`)
- **Functions/Variables**: snake_case (`get_workspace_period`, `budget_period_id`)
- **Constants**: UPPER_SNAKE_CASE (`WRITE_ROLES`, `TOKEN_KEY`)
- **Schemas**: Suffix with purpose (`TransactionCreate`, `TransactionOut`, `TransactionImport`)

### Return Early Pattern

Use guard clauses and early returns to reduce nesting and improve readability:

```python
# Bad: deeply nested
def process_transaction(data):
    if data:
        if data.amount > 0:
            if data.currency:
                return create_transaction(data)
    return None

# Good: return early
def process_transaction(data):
    if not data:
        return None
    if data.amount <= 0:
        return None
    if not data.currency:
        return None
    return create_transaction(data)
```

### Django Ninja Endpoints

Endpoints are thin wrappers — parse the request, call the service, return the response. Business logic belongs in service classes.

For workspace-scoped endpoints, use `WorkspaceJWTAuth` which automatically validates that the user has an active workspace:

```python
from common.auth import WorkspaceJWTAuth
from common.permissions import require_role
from transactions.services import TransactionService
from workspaces.models import WRITE_ROLES

router = Router(tags=['Transactions'])

@router.get('', response=list[TransactionOut], auth=WorkspaceJWTAuth())
def list_transactions(request: HttpRequest, budget_period_id: int | None = Query(None)):
    """Docstring describing the endpoint."""
    workspace_id = request.auth.current_workspace_id
    return TransactionService.list(workspace_id, budget_period_id)

@router.post('', response={201: TransactionOut}, auth=WorkspaceJWTAuth())
def create_transaction(request: HttpRequest, data: TransactionCreate):
    user = request.auth
    workspace_id = request.auth.current_workspace_id
    require_role(user, workspace_id, WRITE_ROLES)
    return 201, TransactionService.create(user, workspace_id, data)
```

For endpoints that don't require an active workspace (e.g., listing all workspaces), use `JWTAuth`:

```python
from common.auth import JWTAuth

@router.get('', response=list[WorkspaceOut], auth=JWTAuth())
def list_workspaces(request: HttpRequest):
    return WorkspaceService.list(request.auth)
```

### Service Layer

Business logic lives in `<app>/services.py` as class-based services (e.g., `TransactionService`). Services handle validation, DB operations, and balance updates. Domain-specific exceptions are defined in `<app>/exceptions.py`.

Shared helpers:
- `common/permissions.py` — `require_role(user, workspace_id, allowed_roles)` — raises 403, returns the role
- `common/services/base.py` — `resolve_currency`, `get_or_create_period_balance`, `update_period_balance`

```python
# transactions/services.py
from django.db import transaction as db_transaction

from common.exceptions import CurrencyNotFoundInWorkspaceError
from common.services.base import get_or_create_period_balance, resolve_currency
from transactions.exceptions import TransactionNoActivePeriodError, TransactionNotFoundError
from transactions.models import Transaction

class TransactionService:
    @staticmethod
    def get_transaction(transaction_id: int, workspace_id: int) -> Transaction:
        trans = Transaction.objects.for_workspace(workspace_id).filter(id=transaction_id).first()
        if not trans:
            raise TransactionNotFoundError()
        return trans

    @staticmethod
    @db_transaction.atomic
    def create(user, workspace_id: int, data: TransactionCreate) -> Transaction:
        currency = resolve_currency(workspace_id, data.currency)
        if not currency:
            raise CurrencyNotFoundInWorkspaceError(data.currency)
        trans = Transaction.objects.create(..., created_by=user, updated_by=user)
        TransactionService.update_period_balance(...)
        return trans
```

### No Nested Helper Functions

Do not define helper functions inside a method body. Extract them as `@staticmethod` methods on the service class. This improves readability, testability, and follows the flat-structure convention used across the codebase.

```python
# Bad — nested functions inside a method
class WorkspaceService:
    def add_member(self, ...):
        def _send_existing(user, workspace):
            ...
        def _send_new(email, workspace):
            ...
        _send_existing(user, workspace)

# Good — class-level static methods
class WorkspaceService:
    @staticmethod
    def _send_existing_invite(user, workspace):
        ...

    @staticmethod
    def _send_new_invite(email, workspace):
        ...

    def add_member(self, ...):
        WorkspaceService._send_existing_invite(user, workspace)
```

### Concurrent Safety with `select_for_update`

For operations that must be atomic under concurrent requests (e.g., consuming a one-time recovery code), use `select_for_update()` to acquire a row-level lock and combine related field updates into a single `save()`:

```python
@staticmethod
@db_transaction.atomic
def verify_code(user: User, code: str) -> bool:
    try:
        twofa = UserTwoFactor.objects.select_for_update().get(user=user, is_enabled=True)
    except UserTwoFactor.DoesNotExist:
        return False

    if _try_recovery_code(twofa, code):
        twofa.last_used_at = timezone.now()
        twofa.save(update_fields=['backup_codes', 'last_used_at', 'updated_at'])
        return True
    return False
```

Without `select_for_update()`, two concurrent requests could both read the same recovery code before either writes, allowing double-use.

### Rate Limiting

Two decorators are available in `common/throttle.py`:

- **`rate_limit(key_prefix, limit, period)`** — Keys by client IP only. Use for most endpoints.
- **`rate_limit_by_key(key_prefix, key_extractor, limit, period)`** — Keys by client IP + custom key (e.g., `user_id` from a temp token). Use when an attacker could rotate IPs to bypass IP-only limits.

All rate limit `limit` and `period` values **must** be configured via Django settings backed by env vars, not hardcoded. Each setting needs an inline comment explaining its purpose:

```python
# Max 2FA verification attempts per IP+user within the period window
RATE_LIMIT_VERIFY_2FA = int(os.getenv('RATE_LIMIT_VERIFY_2FA', '10'))
# Time window (seconds) for 2FA verification rate limiting
RATE_LIMIT_VERIFY_2FA_PERIOD = int(os.getenv('RATE_LIMIT_VERIFY_2FA_PERIOD', '60'))
```

Reference in endpoints via `settings.RATE_LIMIT_*`:

```python
from django.conf import settings
from common.throttle import rate_limit, rate_limit_by_key

@router.post('/verify-2fa', response={200: Token, 401: DetailOut, 404: DetailOut, 429: DetailOut})
@rate_limit_by_key('verify_2fa', _extract_2fa_rate_key, limit=settings.RATE_LIMIT_VERIFY_2FA, period=settings.RATE_LIMIT_VERIFY_2FA_PERIOD)
def verify_2fa(request, data: Verify2FAIn):
    ...
```

### Token Consumption Patterns

Two functions exist in `common/auth.py` for temp tokens:

- **`decode_temp_token(token)`** — Peeks at the token payload without side effects. Use when you need to read claims without consuming the token (e.g., extracting a `user_id` for rate limiting).
- **`consume_temp_token(token)`** — Consumes the token (marks its JTI as used in cache). Returns `None` on replay. Use when the token should be single-use (e.g., `verify_2fa`).

Never use `decode_temp_token` where `consume_temp_token` is appropriate — a consumed token must not be replayable.

### Check Object State, Not Just Existence

When a model has a boolean flag (e.g., `is_enabled`, `is_active`), always check both the object's existence AND the flag. Records can exist in intermediate/disabled states, and a simple truthiness check on the object silently misses `flag=False`.

```python
# Bad — only checks existence, misses is_enabled=False
twofa = UserTwoFactor.objects.filter(user_id=user_id).first()
if not twofa:
    raise TwoFactorNotEnabledError()

# Good — checks existence AND enabled state
twofa = UserTwoFactor.objects.filter(user_id=user_id).first()
if not twofa or not twofa.is_enabled:
    raise TwoFactorNotEnabledError()
```

This applies to any model with status flags: `is_enabled`, `is_active`, `is_verified`, etc.

### Validate Stateful Dependencies Before Operations

When an endpoint or service method depends on a resource being in a specific state, validate that state **before** attempting the main operation. This provides a meaningful, specific error instead of a misleading generic one.

```python
# Bad — user gets "Invalid verification code" when the real issue is 2FA was disabled
@router.post('/verify-2fa')
def verify_2fa(request, data):
    user = get_user(data.temp_token)
    if not TwoFactorService.verify_code(user, data.code):
        return 401, {'detail': 'Invalid verification code'}

# Good — check 2FA state first, then verify the code
@router.post('/verify-2fa', response={200: Token, 401: DetailOut, 404: DetailOut})
def verify_2fa(request, data):
    user = get_user(data.temp_token)
    tf = UserTwoFactor.objects.filter(user=user).first()
    if not tf or not tf.is_enabled:
        raise TwoFactorNotEnabledError()
    if not TwoFactorService.verify_code(user, data.code):
        return 401, {'detail': 'Invalid verification code'}
```

This also applies to service methods that depend on a resource existing — validate and raise **before** creating records. For example, reject creation when no budget period covers the given date, rather than saving an invisible orphan record:

```python
# Bad — saves record with budget_period=None, invisible to the API
period_id = CurrencyExchangeService._find_period_for_date(workspace_id, data.date)
CurrencyExchange.objects.create(budget_period_id=period_id, ...)

# Good — reject creation when no period exists
period_id = CurrencyExchangeService._find_period_for_date(workspace_id, data.date)
if not period_id:
    raise CurrencyExchangeNoPeriodError()
CurrencyExchange.objects.create(budget_period_id=period_id, ...)
```

### Document All Possible Response Status Codes

Every endpoint's `response` parameter must list **all** status codes the endpoint can return, including those from raised exceptions. This serves as documentation and ensures Django Ninja generates accurate API schemas.

```python
# Bad — 404 is possible but not documented
@router.post('/verify-2fa', response={200: Token, 401: DetailOut})
def verify_2fa(request, data):
    raise TwoFactorNotEnabledError()  # returns 404, but it's not in the response schema

# Good — all status codes are documented
@router.post('/verify-2fa', response={200: Token, 401: DetailOut, 404: DetailOut})
def verify_2fa(request, data):
    ...
```

### Pydantic Schemas

```python
from pydantic import BaseModel, ConfigDict, Field

class TransactionCreate(BaseModel):
    """Schema for creating a transaction."""
    date: date
    description: str = Field(..., max_length=500)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., pattern=r'^[A-Z]{3}$')

class TransactionOut(BaseModel):
    """Schema for transaction response."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date
    amount: Decimal
```

### Error Handling

- **Domain Exceptions**: Services raise domain exceptions inheriting from `ServiceError` (in `common/exceptions.py`)
- **Global Handler**: A Django Ninja exception handler in `config/urls.py` converts `ServiceError` to HTTP responses automatically
- **Exception Types**: `NotFoundError` (404), `ValidationError` (400), `AuthenticationError` (401), `PermissionDeniedError` (403)
- **App Exceptions**: Each app defines specific exceptions in `<app>/exceptions.py` (e.g., `TransactionNotFoundError`)
- **Transactions**: Use `@db_transaction.atomic` for database operations that update balances
- **Exception Naming**: `<Domain><ErrorType>Error` — e.g., `TwoFactorNotEnabledError`, `TransactionNotFoundError`. Always set `default_message` and `default_code` as class attributes
- **Exception Codes**: Every domain exception should include a `default_code` (snake_case string) for frontend error matching (e.g., `'two_factor_not_enabled'`, `'invalid_password'`)

```python
# common/exceptions.py
class ServiceError(Exception):
    http_status: int = 500
    default_message: str = 'An unexpected error occurred'
    default_code: str | None = None

class NotFoundError(ServiceError):
    http_status = 404
    default_message = 'Not found'

# users/exceptions.py
class TwoFactorNotEnabledError(NotFoundError):
    default_message = 'Two-factor authentication is not enabled for this user'
    default_code = 'two_factor_not_enabled'

# For exceptions with dynamic messages, accept params in __init__:
class CurrencyNotFoundInWorkspaceError(ValidationError):
    def __init__(self, currency: str):
        super().__init__(f'Currency {currency} not found in workspace', code='currency_not_found')
```

### Testing

Use Factory Boy factories (e.g., `WorkspaceMemberFactory`) instead of direct `Model.objects.create()` calls when creating test database records. Factories exist in `<app>/factories.py` across the codebase.

**Factory gotcha:** Factories for financial records (`TransactionFactory`, `PlannedTransactionFactory`, `CurrencyExchangeFactory`) default to creating their own `BudgetPeriod` and `User` via `SubFactory`. When tests need records tied to a specific workspace/account/period, pass these explicitly:

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

```python
from common.tests.mixins import AuthMixin, APIClientMixin
from django.test import TestCase

class TestTransactions(AuthMixin, APIClientMixin, TestCase):
    user_role = 'member'  # default: 'owner'; also: 'admin', 'viewer'

    def test_create_transaction(self):
        data = self.post('/api/transactions', payload, **self.auth_headers())
        self.assertStatus(201)

    def test_viewer_cannot_create(self):
        # self.user, self.workspace, self.auth_token are available
        self.assertStatus(403)
```

`AuthMixin` creates a workspace with PLN+USD currencies (via `WorkspaceFactory`), a user, a workspace membership, and a default "General" `BudgetAccount`. The mixin also creates an `auth_token` and provides `auth_headers()`.

## Frontend Code Style (TypeScript/React)

### File Structure

- Components: `components/Category/CategoryRow.tsx`
- Pages: `pages/CategoryPage.tsx`
- Types: `types/index.ts`
- API: `api/client.ts`
- Contexts: `contexts/AuthContext.tsx`

### Component Pattern

```tsx
interface Props {
  id: number
  name: string
  onSave?: (data: Category) => void
}

export default function CategoryForm({ id, name, onSave }: Props) {
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      // ...
    } catch (error) {
      toast.error('Failed to save')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      {/* ... */}
    </form>
  )
}
```

### Multi-Step UI Flows

Use a union-typed state machine with conditional rendering for multi-step flows (e.g., setup → verify → confirm):

```typescript
type SectionState = 'idle' | 'setup' | 'showing_codes' | 'disabling'

const [state, setState] = useState<SectionState>('idle')

if (state === 'showing_codes') return <RecoveryCodesDisplay ... />
if (state === 'setup' && setupData) return <SetupForm ... />

const mutation = useMutation({
  mutationFn: api.verifySetup,
  onSuccess: (data) => {
    setState('showing_codes')
    queryClient.invalidateQueries({ queryKey: ['status'] })
  },
})
```

### Auth Response Error Guard

Every auth function that expects an `access_token` in its response must have an `else` branch showing an error toast when the token is missing. Never silently do nothing on an unexpected response:

```typescript
if (response.access_token) {
  // ... existing success logic
} else {
  toast.error('Unexpected response from server. Please try again.')
  return
}
```

### Stateful Component Preservation with CSS `hidden`

When a component holds important transient state (e.g., recovery codes that cannot be re-displayed), use CSS `hidden` to keep it mounted but visually hidden when switching tabs. Conditional rendering (`{condition && <Component />}`) unmounts the component, permanently losing internal state:

```tsx
// Bad — unmounts TwoFactorSection, losing recovery codes
{activeTab === 'security' && <TwoFactorSection />}

// Good — stays mounted, preserving internal state
<div className={activeTab === 'security' ? '' : 'hidden'}>
  <TwoFactorSection />
</div>
```

Only apply this to components where state loss is problematic — other tabs can continue using conditional rendering.

### API Client Pattern

```typescript
export const categoriesApi = {
  getAll: (params?: { budget_period_id?: number }) => 
    api.get('/categories', { params }),
  create: (data: { budget_period_id: number; name: string }) => 
    api.post('/categories', data),
  update: (id: number, data: { budget_period_id: number; name: string }) => 
    api.put(`/categories/${id}`, data),
  delete: (id: number) => 
    api.delete(`/categories/${id}`),
}
```

### Naming Conventions

- **Components**: PascalCase (`BudgetTable`, `TransactionList`)
- **Functions**: camelCase (`handleSubmit`, `fetchData`)
- **Constants**: camelCase for objects, UPPER_SNAKE for primitives
- **Types/Interfaces**: PascalCase (`User`, `Transaction`, `Props`)
- **Event handlers**: `handle` prefix (`handleSubmit`, `handleClick`)

### Imports Order

```typescript
// React/React Router
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

// External libraries
import toast from 'react-hot-toast'

// Internal - API
import { categoriesApi } from '../api/client'

// Internal - Types
import type { Category } from '../types'

// Internal - Contexts/Hooks
import { useAuth } from '../contexts/AuthContext'
```

## Security Model (Four Layers)

1. **Authentication**: `auth=JWTAuth()` on endpoints (or `auth=WorkspaceJWTAuth()` for workspace-scoped endpoints)
2. **Workspace Membership**: Guaranteed by `WorkspaceJWTAuth` — raises 400 if `current_workspace_id` is unset
3. **Role-Based Permissions**: `require_role(user, workspace_id, WRITE_ROLES)`
4. **Resource Ownership**: Filter queries by workspace ID using `Model.objects.for_workspace(workspace_id)`

### Workspace-Scoped Endpoints

For endpoints that require an active workspace, use `WorkspaceJWTAuth`:

```python
from common.auth import WorkspaceJWTAuth

@router.get('', response=list[TransactionOut], auth=WorkspaceJWTAuth())
def list_transactions(request: HttpRequest):
    workspace_id = request.auth.current_workspace_id
    return Transaction.objects.for_workspace(workspace_id)
```

`WorkspaceJWTAuth` returns 400 (not 401) if no workspace is selected, because the token is valid — the workspace state is missing.

### Workspace-Scoped Queries

Use the `for_workspace()` queryset method:

```python
# Instead of:
Transaction.objects.filter(budget_period__budget_account__workspace_id=workspace_id)

# Use:
Transaction.objects.for_workspace(workspace_id)
```

All workspace-scoped models have `WORKSPACE_FILTER` defined.

### List Endpoints Return Empty Arrays for Cross-Workspace Resources

When a list endpoint receives a `budget_period_id` or similar filter that references a resource in another workspace, it returns an empty array (`[]`) rather than 404. This is a deliberate security choice to prevent leaking whether resource IDs exist in other workspaces.

Examples:
- `GET /api/transactions?current_date=...` returns `[]` when no period matches
- `GET /api/categories?budget_period_id=...` returns `[]` when the period belongs to another workspace

Do not "fix" these to return 404 — the empty array behavior is intentional.

## GDPR & Data Integrity Rules

> **When adding or removing a Django model**, always check `backend/users/services.py`:
> - `UserService.delete_account()` — ensure the new model's rows are deleted (or cascade
>   correctly) before parent objects are removed. `on_delete=PROTECT` fields must be deleted
>   in dependency order; otherwise account deletion will raise an `OperationalError`.
> - `UserService.export_all_data()` — include the new model's data in the JSON export so
>   users receive a complete copy of their personal data (GDPR Art. 20). Export only
>   non-sensitive fields (e.g., `is_enabled`, `created_at`, `last_used_at`). Never include
>   secrets, encrypted values, or hashed tokens in the export.

> **When adding new data fields, processing purposes, or third-party integrations**, update
> the legal pages to keep them accurate:
> - `backend/core/templates/legal/privacy-policy.md` — reflect new data collected or how it is used
> - `backend/core/templates/legal/terms-of-service.md` — reflect new features or usage rules
>
> These files use Django template syntax with variables from environment settings:
> - `{{ operator_name }}` — Company or individual name (LEGAL_OPERATOR_NAME)
> - `{{ contact_email }}` — Contact email (LEGAL_CONTACT_EMAIL)
> - `{{ jurisdiction }}` — Legal jurisdiction (LEGAL_JURISDICTION)
> - `{% if is_individual %}...{% endif %}` — Conditional for individuals vs companies
>
> After editing, bump the `version` in the YAML frontmatter to trigger re-consent prompts.
>
> **Deploying legal document updates**: The database is the runtime source of truth for legal
> documents. After bumping template versions, run:
> ```bash
> python manage.py seed_legal_documents          # Seeds from templates if version changed
> python manage.py seed_legal_documents --force  # Force update even if version matches
> ```
> Alternatively, use Django admin to create/edit `LegalDocument` records directly.

## Common Patterns

### Backend: Workspace-scoped Query

```python
# Using the for_workspace() queryset method (preferred)
queryset = Transaction.objects.for_workspace(workspace_id)

# Direct filter (alternative)
queryset = Transaction.objects.filter(
    budget_period__budget_account__workspace_id=workspace.id
)
```

### Backend: Call a Service from an Endpoint

```python
# In api.py — no business logic, just wire up
@router.post('', response={201: TransactionOut}, auth=WorkspaceJWTAuth())
def create_transaction_endpoint(request, data: TransactionCreate):
    user = request.auth
    workspace_id = request.auth.current_workspace_id
    require_role(user, workspace_id, WRITE_ROLES)
    return 201, TransactionService.create(user, workspace_id, data)
```

### Backend: Workspace Management

```python
from workspaces.services import WorkspaceService

# Create a new workspace (auto-switches user to it)
workspace = WorkspaceService.create_workspace(user=user, name='New Workspace', create_demo=True)

# Delete a workspace (switches all affected users to another workspace)
WorkspaceService.delete_workspace(user=user, workspace_id=workspace.id)
```

### Frontend: Use Context

```typescript
const { user, isAuthenticated } = useAuth()
const { workspace, workspaces, switchWorkspace, createWorkspace, deleteWorkspace } = useWorkspace()
const { selectedPeriod, selectedPeriodId } = useBudgetPeriod()
```
