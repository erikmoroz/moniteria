# Code Review Fix Implementation Plan (Round 3)

## Overview

Fix 5 issues found during code review of the `feature/2fa-auth-tests` branch (round 3). Issues range from defense-in-depth security concerns to race conditions in rate limiting and token consumption.

## Issues Summary

| # | Severity | Issue |
|---|----------|-------|
| 1 | MEDIUM | `WorkspaceService.delete_workspace` lacks ownership validation at service layer |
| 2 | LOW-MEDIUM | Invalid temp tokens share a single rate-limit bucket, enabling minor DoS on shared IPs |
| 3 | LOW | TOCTOU race condition in rate limiter (`throttle.py`) |
| 4 | LOW | `consume_temp_token` cache TTL hardcoded to 300s instead of referencing token expiry |
| 5 | LOW | `UserTwoFactor` not explicitly deleted in `UserService.delete_account` |

---

## Task Breakdown

### Task 1: Add ownership validation to `WorkspaceService.delete_workspace`

**Severity: MEDIUM (defense-in-depth)**

**Problem:** `WorkspaceService.delete_workspace` takes a `workspace_id` and fetches the workspace, but does **not** verify that `user` is the owner or even a member. The API layer calls `validate_access` + `require_role(..., [Role.OWNER])` before calling this service, so it's protected at the API level. However, the service method itself has no guard — if another caller invokes `WorkspaceService.delete_workspace` directly (e.g., from a management command or a future endpoint), it would allow any user to delete any workspace.

**Files to modify:**
- `backend/workspaces/services.py` — Add ownership/membership check in `delete_workspace`
- `backend/workspaces/tests/test_services.py` — Add test for non-owner/non-member attempting deletion

**Implementation:**

In `WorkspaceService.delete_workspace()`, after fetching the workspace, verify the user is a member and has owner role:

```python
@staticmethod
@db_transaction.atomic
def delete_workspace(user, workspace_id: int) -> None:
    try:
        workspace = Workspace.objects.select_for_update().get(id=workspace_id)
    except Workspace.DoesNotExist:
        raise WorkspaceNotFoundError()

    membership = WorkspaceMember.objects.filter(user=user, workspace=workspace).select_for_update().first()
    if not membership or membership.role != Role.OWNER:
        raise WorkspacePermissionDeniedError()
    # ... rest of existing logic
```

**Test to add:**

```python
def test_delete_workspace_rejects_non_owner(self):
    # Create workspace with owner, add a non-owner member
    # Call delete_workspace as non-owner
    # Assert WorkspacePermissionDeniedError raised

def test_delete_workspace_rejects_non_member(self):
    # Create workspace with one owner
    # Call delete_workspace as a user who is not a member
    # Assert WorkspacePermissionDeniedError raised
```

**Done criteria:**
- [ ] `delete_workspace` validates caller is an owner of the workspace
- [ ] Non-owner and non-member callers are rejected with 403
- [ ] Existing tests pass (API-layer tests still work since API already validates)

**Verification:**
```bash
cd backend && uv run ruff check --fix . && uv run ruff format .
cd backend && pytest workspaces/tests/ -v
```

---

### Task 2: Fix shared rate-limit bucket for invalid temp tokens

**Severity: LOW-MEDIUM**

**Problem:** In `core/api.py:95`, when an attacker sends a completely invalid/garbage temp_token, `decode_temp_token` returns `None`, and the key extractor returns `'invalid'`. All attackers sending invalid tokens from the same IP share a single rate-limit bucket keyed by `ratelimit:verify_2fa:{ip}:invalid`. An attacker could intentionally exhaust this bucket to temporarily block legitimate 2FA verification for other users on shared IPs (e.g., corporate NAT).

**Files to modify:**
- `backend/core/api.py` — Change `_extract_2fa_rate_key` to use a unique key for invalid tokens

**Implementation:**

Instead of returning a fixed `'invalid'` string, return a random value so each invalid token gets its own bucket:

```python
import uuid

def _extract_2fa_rate_key(request, data: Verify2FAIn = None, **kwargs):
    payload = decode_temp_token(data.temp_token)
    if payload:
        return str(payload.get('user_id', 'unknown'))
    return str(uuid.uuid4())
```

This ensures:
- Valid tokens: rate-limited per (IP, user_id) — same as before
- Invalid tokens: each gets a unique bucket — no shared exhaustion

The existing IP-based rate limiting still applies (same IP can't flood with unlimited unique invalid tokens because the IP portion of the key is shared).

**Done criteria:**
- [ ] Invalid temp tokens no longer share a rate-limit bucket
- [ ] Valid tokens continue to be rate-limited per (IP, user_id)
- [ ] Existing tests pass

**Verification:**
```bash
cd backend && uv run ruff check --fix . && uv run ruff format .
cd backend && pytest core/tests/test_auth.py -v
```

---

### Task 3: Fix TOCTOU race condition in rate limiter

**Severity: LOW**

**Problem:** Both `rate_limit` and `rate_limit_by_key` in `common/throttle.py` perform a non-atomic read-then-write: `cache.get()` then `cache.set()`. Two concurrent requests can both read `count = 9`, both pass the check, and both set `count = 10`, allowing 11 requests through instead of 10.

**Files to modify:**
- `backend/common/throttle.py` — Use atomic cache operations

**Implementation:**

Use Django cache's `add()` + `incr()` pattern for atomic counting:

```python
def rate_limit(key_prefix: str, limit: int = 10, period: int = 60):
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            ip = get_client_ip(request) or 'unknown'
            cache_key = f'ratelimit:{key_prefix}:{ip}'

            count = cache.get(cache_key, 0)
            if count >= limit:
                raise HttpError(429, 'Too many requests. Please try again later.')

            if count == 0:
                cache.add(cache_key, 0, period)
            try:
                cache.incr(cache_key)
            except ValueError:
                cache.set(cache_key, 1, period)

            return func(request, *args, **kwargs)

        return wrapper

    return decorator
```

**Alternative (simpler) approach:** Use `cache.add()` as an atomic "create if not exists" with TTL, then `cache.incr()`:

```python
def _atomic_increment(cache_key: str, period: int) -> int:
    added = cache.add(cache_key, 1, period)
    if added:
        return 1
    try:
        return cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, period)
        return 1
```

Then use in both `rate_limit` and `rate_limit_by_key`:

```python
count = _atomic_increment(cache_key, period)
if count > limit:
    raise HttpError(429, 'Too many requests. Please try again later.')
```

Note: This changes the semantics slightly — the counter now increments *before* the check (increment-first vs check-first). The overage is at most 1 request per concurrent burst, which is acceptable and strictly better than the current unlimited overage.

**Done criteria:**
- [ ] Rate limiter uses atomic cache operations (`add`/`incr`)
- [ ] No TOCTOU race between count read and write
- [ ] Existing tests pass

**Verification:**
```bash
cd backend && uv run ruff check --fix . && uv run ruff format .
cd backend && pytest core/tests/test_auth.py -v
```

---

### Task 4: Derive `consume_temp_token` cache TTL from token expiry

**Severity: LOW**

**Problem:** `consume_temp_token` in `common/auth.py:132` hardcodes `cache.set(cache_key, True, 300)` (5 minutes). The temp token itself has a 5-minute TTL set in `create_temp_token` via `datetime.timedelta(minutes=5)`. If the token TTL is ever changed via settings, the cache TTL won't follow — a consumed token could expire from cache before the JWT expires, allowing replay.

**Files to modify:**
- `backend/common/auth.py` — Derive cache TTL from the token's `exp` claim

**Implementation:**

Read the `exp` claim from the decoded payload and compute remaining TTL:

```python
def consume_temp_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None

    if payload.get('type') != '2fa_pending':
        return None

    jti = payload.get('jti')
    if not jti:
        return None

    cache_key = f'2fa_temp_token_used:{jti}'
    if cache.get(cache_key):
        return None

    exp = payload.get('exp', 0)
    ttl = max(int(exp - datetime.datetime.now(datetime.timezone.utc).timestamp()), 0)
    if ttl == 0:
        return None

    cache.set(cache_key, True, ttl)
    return payload
```

This ensures the cache TTL always matches the remaining token lifetime, regardless of what TTL is configured for temp token creation.

**Done criteria:**
- [ ] Cache TTL derived from token's `exp` claim, not hardcoded
- [ ] No replay possible when token TTL is changed
- [ ] Existing tests pass

**Verification:**
```bash
cd backend && uv run ruff check --fix . && uv run ruff format .
cd backend && pytest core/tests/test_auth.py -v
```

---

### Task 5: Explicitly delete `UserTwoFactor` records in `UserService.delete_account`

**Severity: LOW (defense-in-depth)**

**Problem:** `UserService.delete_account()` explicitly deletes financial records, budget accounts, workspaces, and memberships, but does **not** explicitly delete `UserTwoFactor` records. The model has `on_delete=CASCADE` on the `user` FK, so Django cascade-deletes it when the User is deleted. However, following the pattern established in AGENTS.md for `SET_NULL` children and explicit cleanup, this should be explicit for clarity and robustness. If `delete_account` is later refactored to not delete the User row directly, the 2FA records would remain.

**Files to modify:**
- `backend/users/services.py` — Add explicit `UserTwoFactor` deletion before `user.delete()`

**Implementation:**

In `delete_account()`, before `user.delete()` (line 260), add:

```python
# Delete 2FA records (CASCADE handles this, but explicit for clarity)
from users.models import UserTwoFactor

UserTwoFactor.objects.filter(user=user).delete()

user.delete()
```

Also update `export_all_data` if it references 2FA data — verify the export includes the 2FA records before they're deleted in `delete_account`. The export runs *before* deletion in the current flow, so this is fine.

**Done criteria:**
- [ ] `UserTwoFactor` records explicitly deleted before user deletion
- [ ] Existing tests pass

**Verification:**
```bash
cd backend && uv run ruff check --fix . && uv run ruff format .
cd backend && pytest users/tests/ -v
```

---

## Progress Tracker

- [x] Task 1: Add ownership validation to `WorkspaceService.delete_workspace`
- [x] Task 2: Fix shared rate-limit bucket for invalid temp tokens
- [x] Task 3: Fix TOCTOU race condition in rate limiter
- [ ] Task 4: Derive `consume_temp_token` cache TTL from token expiry
- [ ] Task 5: Explicitly delete `UserTwoFactor` records in `UserService.delete_account`

**Total: 5 tasks**

---

## Agent Prompt Template

```
## Task Assignment

**TASK_NUMBER = [x]**

You are implementing a task from the code review fix plan (round 3).

## Your Task

1. Read the implementation plan at `.ipm/IMPLEMENTATION_PLAN.md`
2. Find Task {TASK_NUMBER} and understand what needs to be done
3. Read all files mentioned in the task's "Files to modify" / "Files to create" sections
4. Read `.ipm/CODING_SUMMARIES.md` for established patterns and style decisions from previous tasks — follow those conventions
5. Implement the changes as specified
6. Run the verification commands listed in the task
7. Ensure all "Done criteria" are satisfied

## Important Rules

- Follow the AGENTS.md coding guidelines
- Backend: run `uv run ruff check --fix .` and `uv run ruff format .` after changes
- Backend: run relevant tests after changes
- Frontend: run `npm run lint` after changes
- Do NOT commit changes unless explicitly asked
- When the user asks to commit changes:
  1. Update the Progress Tracker in `.ipm/IMPLEMENTATION_PLAN.md` (check the box for the completed task)
  2. Update `.ipm/CODING_SUMMARIES.md` — add a new section summarizing the patterns, decisions, and conventions established or reinforced by this task. Include files changed, the pattern name, and a brief description so future tasks can reference it.

## Context

This is part of fixing code review issues found in the `feature/2fa-auth-tests` branch (round 3). The issues are:

1. **Backend**: `WorkspaceService.delete_workspace` lacks ownership validation at service layer — add member+role check
2. **Backend**: Invalid temp tokens share rate-limit bucket `'invalid'` — use `uuid.uuid4()` for unique bucket per invalid token
3. **Backend**: TOCTOU race in `rate_limit` and `rate_limit_by_key` — use atomic `cache.add()`/`cache.incr()` pattern
4. **Backend**: `consume_temp_token` hardcoded 300s cache TTL — derive from token `exp` claim
5. **Backend**: `UserTwoFactor` not explicitly deleted in `delete_account` — add explicit deletion for defense-in-depth

Work on ONLY Task [x]. Do not modify files outside the task's scope.
```
