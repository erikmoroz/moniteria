# Coding Summaries

Established patterns and style decisions captured from implementation tasks. Use this as knowledge for future planning and implementation sessions.

---

## Task 1: Backend — Pagination Schema and Helper Utility

**Files changed:** `backend/core/schemas/pagination.py` (created)

**Pattern: `PaginatedOut[T]` + `paginate_queryset()`**
- `PaginatedOut[T]` is a Pydantic `BaseModel` + `Generic[T]` schema with fields: `items: list[T]`, `total: int`, `page: int`, `page_size: int`, `total_pages: int`. Django Ninja serializes it directly from model instances (via `from_attributes=True` on child schemas).
- `paginate_queryset(queryset, page, page_size)` returns a 5-tuple `(items, total, page, page_size, total_pages)`. Services call this and return a dict with those keys — the API endpoint's `response=PaginatedOut[XxxOut]` handles serialization.
- `ALLOWED_PAGE_SIZES = [25, 50, 100, 200]`, `DEFAULT_PAGE_SIZE = 50` — services import these for parameter defaults.
- Validation: `page_size` not in allowed list → default 50; `page < 1` → default 1; over-page returns empty `items` with correct `total`/`total_pages=0` when total is 0.
- Location: `core/schemas/pagination.py` (alongside other schema modules in `core/schemas/`). Not re-exported from `core/schemas/__init__.py` since it's imported directly by endpoint/service files that need it.

---

## Task 2: Backend — Refactor Planned Transactions List to Service Method

**Files changed:** `backend/planned_transactions/services.py`, `backend/planned_transactions/api.py`

**Pattern: Service-layer extraction for list endpoints**
- Moved inline ORM query from API `list_planned` endpoint into `PlannedTransactionService.list()` static method, following the project convention that API endpoints are thin wrappers and business logic (including queryset construction) lives in the service layer.
- `PlannedTransactionService.list(workspace_id, status=None, budget_period_id=None)` mirrors the existing pattern in `TransactionService.list()`, `CurrencyExchangeService.list()`, `CategoryService.list()`.
- Added `from __future__ import annotations` to `services.py` — required because the method name `list` shadows the builtin, causing `list[dict]` return type annotations on other methods (like `export()`) to fail with `TypeError: 'staticmethod' object is not subscriptable`. All other services with `def list()` already had this import.
- No behavioral changes — all 43 existing tests pass unchanged.

---

## Remediation Task 1: Replace loop-based test creation with `create_batch()`

**Files changed:** `backend/transactions/tests.py`, `backend/planned_transactions/tests/test_planned_transactions.py`, `backend/currency_exchanges/tests/test_currency_exchanges.py`, `backend/categories/tests.py`

**Pattern: Factory Boy `create_batch()` for bulk test data**
- Use `Factory.create_batch(count, **kwargs)` instead of `for` loops when creating multiple test records with identical overrides. This is the idiomatic Factory Boy approach and is more concise.
- For models with `unique_together` constraints (e.g., `Category.unique_together = [['budget_period', 'name']]`), avoid `create_batch` since all instances share the same kwargs and Faker may produce duplicate values. Instead, use a list comprehension with guaranteed-unique field values + `Model.objects.bulk_create()` for a single INSERT query.
- When switching from loops to `create_batch`, per-instance field variation (e.g., `date(2025, 1, i % 28 + 1)`, `name=f'Item {i}'`) can be replaced with a fixed value if the tests only verify count/slicing, not field-specific ordering.
- `create_batch` internally calls `create()` in a loop — it is not a true bulk create. For categories, `bulk_create()` is a genuine single-query optimization.

