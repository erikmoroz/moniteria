# PR Review Remediation Plan — PR #34 (List Pagination)

## Context

These are fixes requested during PR review of the list pagination feature. The original implementation plan (7 tasks) was fully completed. This plan addresses the remaining review feedback.

**PR Comment (planned_transactions/tests line 851):** "You can use bulk create for Factory class, read the documentation of Factory" — Replace loop-based factory creation in pagination test helpers with Factory Boy's `create_batch()`.

---

## Task 1: Replace loop-based test creation with `create_batch()` in all four test files

**Severity: MEDIUM (PR review feedback)**

**Problem:** All four pagination test helpers create records one-by-one in a `for` loop, hitting the DB N times. Factory Boy provides `Factory.create_batch(count, **kwargs)` which is the idiomatic approach.

**Files to modify:**
- `backend/transactions/tests.py` — `TestTransactionPagination._create_transactions()`
- `backend/planned_transactions/tests/test_planned_transactions.py` — `TestPlannedTransactionPagination._create_planned_transactions()`
- `backend/currency_exchanges/tests/test_currency_exchanges.py` — `TestCurrencyExchangePagination._create_exchanges()`
- `backend/categories/tests.py` — `TestCategoryPagination._create_categories()`

**Implementation:**

Replace each loop-based helper with `Factory.create_batch()`. The shared kwargs (workspace, budget_period, currency, user) are passed as overrides to `create_batch()`.

**1. Transactions (`transactions/tests.py`, line ~798):**

```python
# Before:
def _create_transactions(self, count):
    """Create the given number of transactions in the test period."""
    for i in range(count):
        TransactionFactory(
            budget_period=self.period,
            workspace=self.workspace,
            currency=self.pln_currency,
            created_by=self.user,
            updated_by=self.user,
        )

# After:
def _create_transactions(self, count):
    """Create the given number of transactions in the test period."""
    TransactionFactory.create_batch(
        count,
        budget_period=self.period,
        workspace=self.workspace,
        currency=self.pln_currency,
        created_by=self.user,
        updated_by=self.user,
    )
```

**2. Planned Transactions (`planned_transactions/tests/test_planned_transactions.py`, line ~848):**

The original loop uses `planned_date=date(2025, 1, i % 28 + 1)` to vary dates. Since pagination tests don't depend on distinct dates (they test count/slicing only), use a fixed `planned_date`:

```python
# Before:
def _create_planned_transactions(self, count):
    """Create the given number of planned transactions in period1."""
    for i in range(count):
        PlannedTransactionFactory(
            workspace=self.workspace,
            budget_period=self.period1,
            name=f'Planned {i}',
            amount=Decimal('50.00'),
            currency=self.currencies['USD'],
            planned_date=date(2025, 1, i % 28 + 1),
            status='pending',
            created_by=self.user,
            updated_by=self.user,
        )

# After:
def _create_planned_transactions(self, count):
    """Create the given number of planned transactions in period1."""
    PlannedTransactionFactory.create_batch(
        count,
        workspace=self.workspace,
        budget_period=self.period1,
        amount=Decimal('50.00'),
        currency=self.currencies['USD'],
        planned_date=date(2025, 1, 15),
        status='pending',
        created_by=self.user,
        updated_by=self.user,
    )
```

Note: `name` override is removed — the factory default `factory.Faker('sentence')` provides varied names. `planned_date` is set to a fixed date since the tests only verify count/slicing, not date-based ordering. The `name=f'Planned {i}'` was only for readability and is unnecessary since Faker generates unique sentences.

**3. Currency Exchanges (`currency_exchanges/tests/test_currency_exchanges.py`, line ~698):**

Same pattern — original loop uses `date=date(2025, 1, i % 28 + 1)`, replaced with a fixed date:

```python
# Before:
def _create_exchanges(self, count):
    """Create the given number of exchanges in period1."""
    for i in range(count):
        CurrencyExchangeFactory(
            workspace=self.workspace,
            budget_period=self.period1,
            date=date(2025, 1, i % 28 + 1),
            from_currency=self.currencies['USD'],
            from_amount=Decimal('10.00'),
            to_currency=self.currencies['EUR'],
            to_amount=Decimal('9.00'),
            created_by=self.user,
            updated_by=self.user,
        )

# After:
def _create_exchanges(self, count):
    """Create the given number of exchanges in period1."""
    CurrencyExchangeFactory.create_batch(
        count,
        workspace=self.workspace,
        budget_period=self.period1,
        date=date(2025, 1, 15),
        from_currency=self.currencies['USD'],
        from_amount=Decimal('10.00'),
        to_currency=self.currencies['EUR'],
        to_amount=Decimal('9.00'),
        created_by=self.user,
        updated_by=self.user,
    )
```

**4. Categories (`categories/tests.py`, line ~784):**

Categories have a `unique_together = [['budget_period', 'name']]` constraint. The original loop uses `name=f'Category {i}'` to ensure uniqueness. Since `create_batch` passes the same kwargs to every instance, we need a different approach. The `CategoryFactory` already uses `factory.Faker('word')` for names, but Faker may produce duplicates at high counts.

Use `factory.build_batch()` + manual name assignment + `bulk_create()` for categories:

```python
# Before:
def _create_categories(self, count):
    """Create the given number of categories in the test period."""
    for i in range(count):
        CategoryFactory(
            budget_period=self.period,
            name=f'Category {i}',
            created_by=self.user,
        )

# After:
def _create_categories(self, count):
    """Create the given number of categories in the test period."""
    CategoryFactory.create_batch(
        count,
        budget_period=self.period,
        created_by=self.user,
    )
```

Wait — this won't work because `factory.Faker('word')` may produce duplicate names violating the unique constraint. Instead, use `build_batch` + `bulk_create`:

```python
def _create_categories(self, count):
    """Create the given number of categories in the test period."""
    instances = CategoryFactory.build_batch(
        count,
        budget_period=self.period,
        created_by=self.user,
    )
    for i, instance in enumerate(instances):
        instance.name = f'Category {i}'
        instance.workspace = self.workspace
    Category.objects.bulk_create(instances)
```

Actually, the simplest correct approach: keep the loop but use `create_batch` where possible. For categories, since `unique_together` requires unique names, and `create_batch` doesn't support per-instance kwargs, we have two options:

**Option A** — Use `build_batch` + `bulk_create` (1 query instead of N):
```python
def _create_categories(self, count):
    """Create the given number of categories in the test period."""
    categories = [
        Category(
            budget_period=self.period,
            workspace=self.workspace,
            name=f'Category {i}',
            created_by=self.user,
        )
        for i in range(count)
    ]
    Category.objects.bulk_create(categories)
```

**Option B** — Override the factory with `factory.Sequence` for unique names:
This would change the factory's default behavior, which may affect other tests.

**Recommendation:** Use Option A for categories (list comprehension + `bulk_create`), and `create_batch` for the other three where there are no unique constraints.

**Done criteria:**
- [ ] `transactions/tests.py` — `_create_transactions` uses `TransactionFactory.create_batch()`
- [ ] `planned_transactions/tests/test_planned_transactions.py` — `_create_planned_transactions` uses `PlannedTransactionFactory.create_batch()`
- [ ] `currency_exchanges/tests/test_currency_exchanges.py` — `_create_exchanges` uses `CurrencyExchangeFactory.create_batch()`
- [ ] `categories/tests.py` — `_create_categories` uses list comprehension + `Category.objects.bulk_create()` (due to unique constraint)
- [ ] All pagination tests still pass with identical assertions
- [ ] No unused imports left behind (e.g., `Decimal` in planned transactions if no longer needed — check before removing)

**Verification:**
```bash
cd backend && uv run ruff check --fix . && uv run ruff format .
cd backend && pytest transactions/tests.py categories/tests.py planned_transactions/tests/test_planned_transactions.py currency_exchanges/tests/test_currency_exchanges.py -v
```

---

## Progress Tracker

- [x] Task 1: Replace loop-based test creation with `create_batch()` in all four test files

**Total: 1 task**

---

## Dependency Graph

```
Task 1 (replace loops with create_batch) — single standalone task
```

---

## Agent Prompt Template

```
## Task Assignment

**TASK_NUMBER = [1]**

You are implementing a PR review remediation task for the list pagination feature.

## Your Task

1. Read the implementation plan at `.ipm/IMPLEMENTATION_PLAN.md`
2. Find Task {TASK_NUMBER} and understand what needs to be done
3. Read all files mentioned in the task's "Files to modify" sections
4. Implement the changes as specified
5. Run the verification commands listed in the task
6. Ensure all "Done criteria" are satisfied

## Important Rules

- Follow the AGENTS.md coding guidelines
- Backend: run `uv run ruff check --fix .` and `uv run ruff format .` after changes
- Backend: run relevant tests after changes
- Do NOT commit changes unless explicitly asked
- When the user asks to commit changes:
  1. Update the Progress Tracker in `.ipm/IMPLEMENTATION_PLAN.md` (check the box for the completed task)
  2. Update `.ipm/CODING_SUMMARIES.md` — add a new section summarizing the patterns, decisions, and conventions established or reinforced by this task. Include files changed, the pattern name, and a brief description so future tasks can reference it.

## Context

This is a PR review fix for PR #34 (list pagination). The reviewer requested replacing loop-based Factory calls in test helpers with Factory Boy's `create_batch()` method. This affects the pagination test helpers in four test files: transactions, planned transactions, currency exchanges, and categories. The categories helper needs special handling due to a `unique_together` constraint on `(budget_period, name)`.
```

<!--
ORIGINAL PLAN PROGRESS (preserved for reference):
- [x] Task 1: Backend — Create pagination schema and helper utility
- [x] Task 2: Backend — Refactor planned transactions list to service method
- [x] Task 3: Backend — Add pagination to all four list endpoints and services
- [x] Task 4: Backend — Tests for pagination
- [x] Task 5: Frontend — Add `PaginatedResponse` type and `Pagination` component
- [x] Task 6: Frontend — Update Transactions page with pagination
- [x] Task 7: Frontend — Update Planned, Exchanges, and Categories pages with pagination
-->
