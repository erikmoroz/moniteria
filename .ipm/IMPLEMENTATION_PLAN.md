# Code Review Fixes — Email Infrastructure (Round 4)

## Overview

Fix six issues found during code review of the email infrastructure feature branch (round 4):

1. **`LoginIn` and `RegisterIn` still have duplicate `field_validator` for email** — Both schemas define their own `validate_email` classmethod instead of using the shared `ValidatedEmail` type. Same behavior today, but risks drift with the other schemas that already use `ValidatedEmail`.
2. **`resend_verification` mixes API-level concerns into the service layer** — Returns the anti-enumeration message string and includes `time.sleep()` timing normalization. Per AGENTS.md, timing normalization and response messages belong in the API layer.
3. **`forgot_password` endpoint does direct DB queries** — Inlines `User.objects.filter()` and timing normalization instead of delegating to a service method, inconsistent with how other endpoints are structured.
4. **`ConfirmEmailChangePage` behind `ProtectedRoute`** — Users clicking the email link in a different browser or after session expiry must re-authenticate. Known UX trade-off; documented, no code change.
5. **No frontend `forgotPassword` / `resetPassword` API methods** — Frontend coverage is incomplete for the password reset flow.
6. **`TOKEN_MAX_AGE` parsed with bare `int(os.getenv(...))`** — Crashes at startup with `ValueError` if the env var is non-numeric.

---

## Progress Tracker

- [x] Task 1: Backend — Replace duplicate email validators in `LoginIn` and `RegisterIn` with `ValidatedEmail`
- [x] Task 2: Backend — Move `resend_verification` anti-enumeration concerns to API layer
- [ ] Task 3: Backend — Extract `forgot_password` logic into a service method
- [ ] Task 4: Document — `ConfirmEmailChangePage` ProtectedRoute UX trade-off (no code change)
- [ ] Task 5: Frontend — Add `forgotPassword` and `resetPassword` API methods
- [ ] Task 6: Backend — Add safe parsing for `TOKEN_MAX_AGE` env var

---

## Task 1: Backend — Replace duplicate email validators in `LoginIn` and `RegisterIn` with `ValidatedEmail`

**Context budget: ~1k tokens**

### Goal

Replace the manual `field_validator('email')` on `LoginIn` and `RegisterIn` with the shared `ValidatedEmail` annotated type, making all email fields across the codebase consistent.

### Background

Round 3 (Task 4) extracted a shared `ValidatedEmail` type and applied it to `ResendVerificationIn`, `ForgotPasswordIn`, and `EmailChangeRequestIn`. However, `LoginIn` and `RegisterIn` were intentionally left with their own `field_validator` because "those schemas have additional validators and may diverge." On review, both email validators are identical to `_validate_email` and there's no realistic divergence scenario — the email validation logic is stable. Keeping two code paths creates drift risk and confuses readers.

### Files to modify

- `backend/core/schemas/auth.py`

### Implementation details

#### `core/schemas/auth.py`

1. In `LoginIn`, replace `email: str` with `email: ValidatedEmail` and remove the `validate_email` classmethod.

2. In `RegisterIn`, replace `email: str` with `email: ValidatedEmail` and remove the `validate_email` classmethod (lines 87-97). Keep the other two field validators (`validate_terms_version`, `validate_privacy_version`) unchanged.

3. After removing both validators, check if `field_validator` is still imported. If only `Field` remains from pydantic, update the import:
   ```python
   from pydantic import BaseModel, Field
   ```
   (Remove `field_validator` from the import if unused elsewhere in the file.)

### Done criteria

- [ ] `LoginIn.email` typed as `ValidatedEmail`
- [ ] `RegisterIn.email` typed as `ValidatedEmail`
- [ ] Both `validate_email` classmethods removed
- [ ] Unused imports cleaned up
- [ ] Linting passes
- [ ] Auth-related tests pass

### Verification commands

```bash
cd backend
uv run ruff check --fix . && uv run ruff format .
pytest core/tests/ -v
```

---

## Task 2: Backend — Move `resend_verification` anti-enumeration concerns to API layer

**Context budget: ~2k tokens**

### Goal

Refactor `UserService.resend_verification` so the service only handles business logic (lookup + send email). The anti-enumeration message string and `time.sleep()` timing normalization move to the API endpoint in `core/api.py`.

### Background

Per AGENTS.md: *"Service layer responsibilities: business logic (validation, DB operations, side effects, balance updates, email notifications)."* The anti-enumeration response message and timing normalization are HTTP-layer concerns, not business logic. Currently the service returns the message string and includes `time.sleep()`, making it aware of the anti-enumeration strategy.

The `forgot_password` endpoint (in `core/api.py`) already handles timing normalization correctly in the API layer — this task brings `resend_verification` to the same pattern.

### Files to modify

- `backend/users/services.py`
- `backend/core/api.py`

### Implementation details

#### `users/services.py` — `resend_verification` method (lines 151-172)

Refactor to only handle business logic. Remove the message string return and the `time.sleep()`. The method should either send the email or do nothing:

```python
@staticmethod
def resend_verification(email: str) -> None:
    user = User.objects.filter(email=email).first()
    if not user or user.email_verified:
        return

    token = generate_verification_token(user.id)
    verification_url = f'{settings.FRONTEND_URL}/verify-email?token={token}'

    EmailService.send_email(
        to=user.email,
        subject='Verify your email — Monie',
        template_name='email/verify_email',
        context={
            'user_name': user.full_name or user.email,
            'verification_url': verification_url,
        },
    )
```

If `random` and `time` are no longer used elsewhere in the file after this change, remove those imports.

#### `core/api.py` — `resend_verification` endpoint (lines 119-124)

Move the anti-enumeration message and timing normalization to the endpoint:

```python
@router.post('/resend-verification', response={200: MessageOut, 429: DetailOut})
@rate_limit('resend_verification', limit=3, period=3600)
def resend_verification(request, data: ResendVerificationIn):
    from users.services import UserService

    message = 'If your email is unverified, a new verification email has been sent.'
    UserService.resend_verification(data.email)
    return 200, {'message': message}
```

**Note on timing normalization:** The service now returns `None` regardless of whether it sent an email, so the endpoint always follows the same code path (no early return). The email-sending path is naturally slower. To normalize timing, you could either:

- **Option A (simple):** Accept that the timing difference is small enough given rate limiting (3/hour). The endpoint always returns the same response regardless of input — the anti-enumeration property is preserved.
- **Option B (thorough):** Add `time.sleep(random.uniform(0.1, 0.3))` in the service's early-return path (before `return`), keeping timing normalization in the service but not the message string. This is a reasonable compromise since the delay is a side effect, not an HTTP concern.

Choose Option A unless timing normalization was explicitly required in previous rounds. If the `forgot_password` endpoint has timing normalization, use Option B for consistency.

### Done criteria

- [ ] `UserService.resend_verification` returns `None` (not a message string)
- [ ] Anti-enumeration message lives in the API endpoint
- [ ] No `time.sleep()` in the service method
- [ ] Unused imports removed from `users/services.py`
- [ ] Linting passes
- [ ] Tests pass

### Verification commands

```bash
cd backend
uv run ruff check --fix . && uv run ruff format .
pytest core/tests/test_email_verification.py -v
```

---

## Task 3: Backend — Extract `forgot_password` logic into a service method

**Context budget: ~2k tokens**

### Goal

Move the `forgot_password` endpoint's inline DB lookup and email-sending logic into `UserService.send_reset_password_email`, making the endpoint a thin wrapper consistent with other endpoints in the codebase.

### Background

`core/api.py:129-141` directly queries `User.objects.filter(email=data.email).first()` and calls `UserService.send_reset_password_email(user)`. Per AGENTS.md, endpoints should be thin wrappers — parse request, call service, return response. The user lookup and timing normalization belong in the service layer alongside the email-sending logic.

This also aligns with how `resend_verification` works (after Task 2): the service handles lookup + send, the endpoint handles response formatting.

### Files to modify

- `backend/users/services.py`
- `backend/core/api.py`

### Implementation details

#### `users/services.py` — enhance `send_reset_password_email` to handle user lookup

The existing `send_reset_password_email` method takes a `User` object. Change it to accept an email string and handle the lookup internally:

```python
@staticmethod
def send_reset_password_email(email: str) -> None:
    user = User.objects.filter(email=email).first()
    if not user:
        time.sleep(random.uniform(0.1, 0.3))
        return

    # ... existing token generation and email sending logic
```

Check the current implementation of `send_reset_password_email` to see what it already does — if it already takes a `User`, add a new classmethod or modify the signature. Read the full method first.

**Important:** Ensure `random` and `time` are imported in `users/services.py` if they aren't already (they may have been removed in Task 2).

#### `core/api.py` — simplify `forgot_password` endpoint

```python
@router.post('/forgot-password', response={200: MessageOut, 429: DetailOut})
@rate_limit('forgot_password', limit=3, period=3600)
def forgot_password(request, data: ForgotPasswordIn):
    from users.services import UserService

    UserService.send_reset_password_email(data.email)
    return 200, {'message': 'If an account exists with this email, a reset link has been sent.'}
```

Remove the `User` import from `core/api.py` if it's no longer used elsewhere in the file. Similarly, remove `random` and `time` imports if they're no longer used.

### Done criteria

- [ ] `forgot_password` endpoint is a thin wrapper (no direct DB queries)
- [ ] User lookup and timing normalization moved to service layer
- [ ] Anti-enumeration message stays in the endpoint
- [ ] Unused imports cleaned up in `core/api.py`
- [ ] Linting passes
- [ ] Password reset tests pass

### Verification commands

```bash
cd backend
uv run ruff check --fix . && uv run ruff format .
pytest core/tests/test_password_reset.py -v
```

---

## Task 4: Document — `ConfirmEmailChangePage` ProtectedRoute UX trade-off

**Context budget: ~0.5k tokens**

### Goal

Add a code comment documenting the UX trade-off of requiring authentication for `ConfirmEmailChangePage`.

### Background

`App.tsx:77` wraps `ConfirmEmailChangePage` in `ProtectedRoute`. The backend endpoint uses `JWTAuth()` — the email change token is self-contained (contains user ID + new email) and the backend validates `user.id != user_id` against the authenticated user. If a user clicks the link in a different browser or after session expiry, they're redirected to login with no context. After logging in, they'd need to click the link again.

A full fix would require `ProtectedRoute` to preserve query params through the login redirect, which affects all protected pages — out of scope for this round.

### Files to modify

- `frontend/src/App.tsx`

### Implementation details

#### `App.tsx` — line 77

Add a brief comment above the route:

```tsx
{/* Requires auth: email change token is validated against the logged-in user's ID.
    Users opening the link in a new session must log in first, then re-click the link. */}
<Route path="/confirm-email-change" element={<ProtectedRoute><ConfirmEmailChangePage /></ProtectedRoute>} />
```

### Done criteria

- [ ] Comment added explaining the trade-off
- [ ] No functional changes
- [ ] Frontend lint passes

### Verification commands

```bash
cd frontend
npm run lint
```

---

## Task 5: Frontend — Add `forgotPassword` and `resetPassword` API methods

**Context budget: ~1k tokens**

### Goal

Add `forgotPassword` and `resetPassword` methods to the frontend `authApi` object so the password reset pages can be built without additional API plumbing.

### Background

The backend already has `POST /api/auth/forgot-password` and `POST /api/auth/reset-password` endpoints. The frontend `authApi` object is missing corresponding methods. Adding them now ensures the API layer is ready when the reset password UI is built.

### Files to modify

- `frontend/src/api/client.ts` (or wherever `authApi` is defined — verify the path first)

### Implementation details

#### API client — `authApi` object

Add two new methods:

```typescript
forgotPassword: (email: string) =>
  api.post('/auth/forgot-password', { email }),

resetPassword: (data: { uidb64: string; token: string; new_password: string }) =>
  api.post('/auth/reset-password', data),
```

Follow the existing patterns in `authApi` for error handling and return types.

### Done criteria

- [ ] `forgotPassword` method added to `authApi`
- [ ] `resetPassword` method added to `authApi`
- [ ] Method signatures match backend endpoint schemas
- [ ] Frontend lint passes

### Verification commands

```bash
cd frontend
npm run lint
```

---

## Task 6: Backend — Add safe parsing for `TOKEN_MAX_AGE` env var

**Context budget: ~0.5k tokens**

### Goal

Handle non-numeric `TOKEN_MAX_AGE` env var gracefully instead of crashing at startup with an unhandled `ValueError`.

### Background

`config/settings.py:13` uses `int(os.getenv('TOKEN_MAX_AGE', 7 * 24 * 60 * 60))`. If someone sets `TOKEN_MAX_AGE=7d` or similar, `int()` raises `ValueError` at import time. While this fails immediately and is easy to diagnose, wrapping it in a try/except with a clear error message is more helpful.

### Files to modify

- `backend/config/settings.py`

### Implementation details

#### `config/settings.py` — line 13

Replace the bare `int()` call with safe parsing:

```python
_default_token_max_age = 7 * 24 * 60 * 60
try:
    TOKEN_MAX_AGE = int(os.getenv('TOKEN_MAX_AGE', _default_token_max_age))
except (ValueError, TypeError):
    raise ValueError(
        f'TOKEN_MAX_AGE must be an integer, got: {os.getenv("TOKEN_MAX_AGE")!r}'
    )
```

This keeps the crash-on-startup behavior (which is correct — a misconfigured token age is a deployment error) but gives a clear message about what's wrong.

### Done criteria

- [ ] `TOKEN_MAX_AGE` parsing handles `ValueError` and `TypeError`
- [ ] Error message clearly indicates the expected type and the bad value
- [ ] Linting passes

### Verification commands

```bash
cd backend
uv run ruff check --fix . && uv run ruff format .
python -c "from config.settings import TOKEN_MAX_AGE; print(TOKEN_MAX_AGE)"
```

---

## Agent Prompt Template

```
## Task Assignment

**TASK_NUMBER = [x]**

You are implementing a task from the code review fix plan (round 4).

## Your Task

1. Read the implementation plan at `.ipm/IMPLEMENTATION_PLAN.md`
2. Find Task {TASK_NUMBER} and understand what needs to be done
3. Read all files mentioned in the task's "Files to modify" / "Files to create" sections
4. Read AGENTS.md for coding conventions
5. Read `.ipm/CODING_SUMMARIES.md` for established patterns and style decisions from previous tasks — follow those conventions
6. Implement the changes as specified
7. Run the verification commands listed in the task
8. Ensure all "Done criteria" are satisfied

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

This is part of fixing code review issues found in the email infrastructure feature (round 4). The issues are:

1. **Backend (Structure)**: `LoginIn` and `RegisterIn` have duplicate email `field_validator` — should use shared `ValidatedEmail`
2. **Backend (Structure)**: `resend_verification` service returns anti-enumeration message and includes timing normalization — HTTP concerns belong in API layer
3. **Backend (Structure)**: `forgot_password` endpoint does direct DB queries — should delegate to a service method
4. **Documentation**: `ConfirmEmailChangePage` behind `ProtectedRoute` — add comment documenting UX trade-off
5. **Frontend**: Missing `forgotPassword` and `resetPassword` API methods — add to `authApi`
6. **Backend (Robustness)**: `TOKEN_MAX_AGE` bare `int(os.getenv(...))` crashes on non-numeric input — add safe parsing

Work on ONLY Task [x]. Do not modify files outside the task's scope.
```
