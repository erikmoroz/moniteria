# Email Backend Implementation Plan

## Overview

Add email functionality to the Monie backend for authentication flows, account management, and workspace event notifications. Uses direct SMTP (Google/ProtonMail), synchronous sending via `db_transaction.on_commit`, and Django's template engine for HTML+plain text emails.

## Email Inventory (12 emails, 26 template files + 2 base templates)

| # | Email | Recipient | Trigger |
|---|-------|-----------|---------|
| 1 | Email Verification | New user | Registration |
| 2 | Welcome | New user | Registration |
| 3 | Password Reset | User | Forgot password |
| 4 | Password Changed | User | Password changed (self or admin) |
| 5 | Email Change - Verify | New address | User requests email change |
| 6 | Email Change - Notify | Old address | Email change confirmed |
| 7 | Invitation (new user) | New user | Admin adds to workspace |
| 8 | Invitation (existing) | Existing user | Admin adds to workspace |
| 9 | Member Removed | Removed user | Admin removes member |
| 10 | Member Left | Workspace admins | Member leaves |
| 11 | Workspace Deleted | All other members | Owner deletes workspace |
| 12 | Role Changed | Affected member | Admin changes role |

## Design Decisions

- **SMTP provider**: Direct SMTP (Google App Passwords or ProtonMail Bridge)
- **Sending pattern**: Synchronous via `db_transaction.on_commit` — Celery deferred to future epic
- **Email verification tokens**: Django's `TimestampSigner` (stateless, 7-day expiry, no DB storage)
- **Password reset tokens**: Django's built-in `PasswordResetTokenGenerator` (one-time-use)
- **Email change flow**: `pending_email` field on User; old email stays active until new one is verified
- **Unverified access**: Full access — verification encouraged but not required
- **Templates**: HTML + plain text for every email, shared base layout
- **Workspace invitation**: Keep current admin-creates-account flow, add email notification

## Architecture

### New files
```
backend/
  common/
    email.py                    # EmailService class
    tokens.py                   # TimestampSigner-based token helpers
  templates/
    email/
      base.html                 # Shared HTML layout
      base.txt                  # Shared plain text layout
      verify_email.html/.txt
      welcome.html/.txt
      reset_password.html/.txt
      password_changed.html/.txt
      email_change_verify.html/.txt
      email_change_notify.html/.txt
      workspace_invitation_new.html/.txt
      workspace_invitation_existing.html/.txt
      member_removed.html/.txt
      member_left.html/.txt
      workspace_deleted.html/.txt
      role_changed.html/.txt
```

### Modified files
```
backend/
  config/settings.py            # TEMPLATES DIRS, add FRONTEND_URL
  core/schemas/users.py         # Remove email from UserUpdate, add email_verified to UserOut
  core/schemas/auth.py          # New schemas: forgot/reset, verify, email change
  core/api.py                   # New auth endpoints, registration sends emails
  users/models.py               # Add email_verified, pending_email fields
  users/services.py             # update_profile locks email, change_password sends email
  users/exceptions.py           # New exceptions
  workspaces/services.py        # Add email sends to add_member, leave, remove_member, update_role, delete_workspace
  workspaces/api.py             # Add reset-password email notification
  core/tests/test_auth.py       # Tests for new auth endpoints
  users/tests/                  # Tests for email change, password changed
  workspaces/tests/             # Tests for workspace event emails
  example.env                   # Add SMTP + FRONTEND_URL vars
frontend/
  src/
    api/client.ts               # New API methods
    App.tsx                     # New routes
    pages/                      # New pages: forgot/reset password, verify email, email change
```

---

## Progress Tracker

- [x] Task 1: Email Infrastructure
- [x] Task 2: Base Email Templates
- [x] Task 3: User Model Changes
- [x] Task 4: Email Verification + Welcome Emails
- [x] Task 5: Password Reset + Password Changed Emails
- [x] Task 6: Email Change Flow
- [x] Task 7: Workspace Invitation Emails
- [x] Task 8: Workspace Event Notification Emails
- [ ] Task 9: Frontend — Password Reset Pages
- [x] Task 10: Frontend — Email Verification & Change Pages
- [ ] Task 11: Integration Tests & Cleanup

---

## Task 1: Email Infrastructure

**Context budget: ~12k tokens**

### Goal
Create the `EmailService` class and configure Django to send real emails via SMTP.

### Files to create
- `backend/common/email.py`

### Files to modify
- `backend/config/settings.py`
- `backend/example.env`
- `backend/core/schemas/users.py`
- `backend/users/services.py`
- `backend/common/auth.py`

### Implementation details

#### 1. `common/email.py` — EmailService

```python
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def send_email(
        to: str | list[str],
        subject: str,
        template_name: str,
        context: dict | None = None,
        from_email: str | None = None,
    ) -> bool:
        """
        Send an HTML + plain text email using Django templates.

        Args:
            to: Recipient email(s)
            subject: Email subject line
            template_name: Template name without extension (e.g., 'email/welcome')
                           Must exist as both .html and .txt in templates directory
            context: Dict passed to Django template rendering
            from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)

        Returns:
            True if send succeeded, False otherwise
        """
        context = context or {}
        context.setdefault('frontend_url', getattr(settings, 'FRONTEND_URL', 'http://localhost:5173'))

        try:
            text_content = render_to_string(f'{template_name}.txt', context)
            html_content = render_to_string(f'{template_name}.html', context)

            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email or settings.DEFAULT_FROM_EMAIL,
                to=to if isinstance(to, list) else [to],
            )
            msg.attach_alternative(html_content, 'text/html')
            msg.send(fail_silently=False)
            return True
        except Exception:
            logger.exception('Failed to send email "%s" to %s', subject, to)
            return False
```

#### 2. `config/settings.py` — Add FRONTEND_URL and TEMPLATES DIRS

After `BASE_DIR` definition (line 9), add:
```python
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')
```

In `TEMPLATES[0]` (line 78), change `'DIRS': []` to:
```python
'DIRS': [BASE_DIR / 'templates'],
```

#### 3. `example.env` — Add email configuration variables

Add these lines:
```
# Email (SMTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=noreply@monie.app

# Frontend URL (used in email links)
FRONTEND_URL=http://localhost:5173
```

#### 4. `core/schemas/users.py` — Lock down email changes via PATCH /me

Remove the `email` field from `UserUpdate`:
```python
class UserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None
```

Remove the `validate_email` field_validator on the class (no longer needed).

Add `email_verified` to `UserOut`:
```python
class UserOut(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    current_workspace_id: int | None = None
    is_active: bool
    email_verified: bool = False
    created_at: str
```

#### 5. `users/services.py` — Remove email from update_profile

In `update_profile()` (line 47), remove the `if data.email is not None:` block:
```python
@staticmethod
def update_profile(user: User, data: UserUpdate) -> User:
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.is_active is not None:
        user.is_active = data.is_active
    user.save()
    return user
```

#### 6. `common/auth.py` — Add email_verified to user_to_schema

In `user_to_schema()` (line 82), add `email_verified`:
```python
def user_to_schema(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        current_workspace_id=user.current_workspace_id if user.current_workspace_id else None,
        is_active=user.is_active,
        email_verified=getattr(user, 'email_verified', True),
        created_at=user.created_at.isoformat(),
    )
```

Note: `getattr` with default `True` ensures compatibility before Task 3 migration runs.

### Done criteria
- [ ] `EmailService.send_email()` works with console backend
- [ ] `TEMPLATES[0]['DIRS']` points to `backend/templates/`
- [ ] `FRONTEND_URL` setting is configurable via env
- [ ] `example.env` has all email-related vars with comments
- [ ] `PATCH /api/users/me` no longer accepts `email` field
- [ ] `UserOut` includes `email_verified` field
- [ ] Existing tests still pass

### Verification commands
```bash
cd backend
uv run ruff check --fix . && uv run ruff format .
pytest users/tests/test_users.py -v
pytest core/tests/test_auth.py -v
```

---

## Task 2: Base Email Templates

**Context budget: ~8k tokens**

### Goal
Create the shared HTML and plain text base templates that all emails extend.

### Files to create
- `backend/templates/email/base.html`
- `backend/templates/email/base.txt`

### Implementation details

#### `templates/email/base.html`

Responsive HTML email template with:
- **Inline CSS only** (email clients strip `<style>` tags)
- Max-width 600px, centered with gray background (`#f3f4f6`)
- White content card with 24px padding
- Monie logo/name in header
- Blocks: `{% block preheader %}`, `{% block content %}`, `{% block cta_url %}`, `{% block cta_text %}`
- CTA button: `background: #2563eb`, white text, 8px border-radius, 16px padding
- Footer: "You're receiving this because you have a Monie account."

Variables available in all child templates:
- `{{ user_name }}` — Full name or email
- `{{ frontend_url }}` — Frontend base URL

Template style:
- Font: `system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`
- Primary color: `#2563eb` (blue-600)
- Background: `#f3f4f6` (gray-100)
- Card: `#ffffff`
- Text: `#111827` (gray-900)
- Secondary text: `#6b7280` (gray-500)

#### `templates/email/base.txt`

Plain text companion with:
- Separator line `———`
- Monie name at top
- `{% block content %}`
- Full URL printed for CTA links (no buttons)
- Footer

### Done criteria
- [ ] `base.html` renders with sample context in Django shell
- [ ] `base.txt` renders with sample context
- [ ] Both templates have `{% block content %}`, `{% block preheader %}`
- [ ] HTML template uses inline CSS only
- [ ] `templates/` directory is inside `backend/`

### Verification commands
```bash
cd backend
python manage.py shell -c "
from django.template.loader import render_to_string
ctx = {'user_name': 'Test', 'frontend_url': 'http://localhost:5173'}
print(render_to_string('email/base.html', ctx)[:200])
print(render_to_string('email/base.txt', ctx)[:200])
"
```

---

## Task 3: User Model Changes

**Context budget: ~10k tokens**

### Goal
Add `email_verified` and `pending_email` fields to the User model with a data migration.

### Files to modify
- `backend/users/models.py`
- `backend/users/migrations/` (new migration file)

### Implementation details

#### `users/models.py` — Add fields to User model

Add these fields to the `User` class (after `is_staff`, around line 45):
```python
email_verified = models.BooleanField(default=False)
pending_email = models.EmailField(max_length=255, blank=True, default='')
```

#### Migration

Create migration:
```bash
python manage.py makemigrations users
```

Then **edit the generated migration** to include a data migration that sets `email_verified=True` for all existing users. They registered before verification existed, so we grandfather them in.

The data migration should be a separate `RunPython` operation in the same migration file:
```python
from django.db import migrations


def set_existing_verified(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.all().update(email_verified=True)


class Migration(migrations.Migration):
    dependencies = [
        ('users', '<previous_migration>'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='pending_email',
            field=models.EmailField(blank=True, default='', max_length=255),
        ),
        migrations.RunPython(set_existing_verified, migrations.RunPython.noop),
    ]
```

### Done criteria
- [ ] Migration runs without errors
- [ ] Existing users have `email_verified=True`
- [ ] New users default to `email_verified=False`
- [ ] `pending_email` defaults to empty string
- [ ] All existing tests pass (no fields were required)

### Verification commands
```bash
cd backend
python manage.py makemigrations users
python manage.py migrate
pytest core/tests/ -v
pytest users/tests/ -v
```

---

## Task 4: Email Verification + Welcome Emails

**Context budget: ~18k tokens**

### Goal
Implement email verification flow and welcome email, both sent on registration.

### Files to create
- `backend/common/tokens.py`
- `backend/templates/email/verify_email.html`
- `backend/templates/email/verify_email.txt`
- `backend/templates/email/welcome.html`
- `backend/templates/email/welcome.txt`
- `backend/core/tests/test_email_verification.py`

### Files to modify
- `backend/core/api.py`
- `backend/core/schemas/auth.py`
- `backend/core/schemas/__init__.py`
- `backend/users/exceptions.py`

### Implementation details

#### 1. `common/tokens.py` — Verification token helpers

Use Django's `TimestampSigner` for stateless tokens (no DB storage needed):

```python
from django.core.signing import TimestampSigner


def generate_verification_token(user_id: int) -> str:
    signer = TimestampSigner()
    return signer.sign(str(user_id))


def verify_verification_token(token: str, max_age: int = 7 * 24 * 60 * 60) -> int | None:
    """
    Verify a verification token.
    Returns user_id if valid, None if expired or invalid.
    max_age defaults to 7 days (604800 seconds).
    """
    signer = TimestampSigner()
    try:
        value = signer.unsign(token, max_age=max_age)
        return int(value)
    except Exception:
        return None


def generate_email_change_token(user_id: int, new_email: str) -> str:
    signer = TimestampSigner()
    return signer.sign_object({'uid': user_id, 'email': new_email})


def verify_email_change_token(token: str, max_age: int = 7 * 24 * 60 * 60) -> tuple[int, str] | None:
    signer = TimestampSigner()
    try:
        data = signer.unsign_object(token, max_age=max_age)
        return data['uid'], data['email']
    except Exception:
        return None
```

Note: We include `generate_email_change_token` and `verify_email_change_token` here even though they're used in Task 6, so the file is created once with all token helpers.

#### 2. `core/schemas/auth.py` — New schemas

Add to the existing file:

```python
class VerifyEmailIn(BaseModel):
    token: str


class ResendVerificationIn(BaseModel):
    email: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        validator = EmailValidator()
        try:
            validator(v)
        except DjangoValidationError:
            raise ValueError('Enter a valid email address')
        return v
```

Update `core/schemas/__init__.py` to export the new schemas.

#### 3. `users/exceptions.py` — New exceptions

```python
class UserAlreadyVerifiedError(ValidationError):
    default_message = 'Email is already verified'


class UserInvalidVerificationTokenError(ValidationError):
    default_message = 'Invalid or expired verification token'
```

#### 4. `core/api.py` — New endpoints

Add imports at top:
```python
from common.email import EmailService
from common.tokens import generate_verification_token, verify_verification_token
```

Add two new endpoints:

**Verify email:**
```python
@router.post('/verify-email', response={200: MessageOut, 400: DetailOut})
def verify_email(request, data: VerifyEmailIn):
    user_id = verify_verification_token(data.token)
    if not user_id:
        return 400, {'detail': 'Invalid or expired verification token'}
    user = User.objects.filter(id=user_id).first()
    if not user:
        return 400, {'detail': 'User not found'}
    if user.email_verified:
        return 400, {'detail': 'Email is already verified'}
    user.email_verified = True
    user.save(update_fields=['email_verified'])
    return 200, {'message': 'Email verified successfully'}
```

**Resend verification:**
```python
@router.post('/resend-verification', response={200: MessageOut, 429: DetailOut})
@rate_limit('resend_verification', limit=3, period=3600)
def resend_verification(request, data: ResendVerificationIn):
    user = User.objects.filter(email=data.email).first()
    if not user or user.email_verified:
        return 200, {'message': 'If your email is unverified, a new verification email has been sent.'}

    token = generate_verification_token(user.id)
    verification_url = f'{settings.FRONTEND_URL}/verify-email?token={token}'

    def _send():
        EmailService.send_email(
            to=user.email,
            subject='Verify your email — Monie',
            template_name='email/verify_email',
            context={
                'user_name': user.full_name or user.email,
                'verification_url': verification_url,
            },
        )

    db_transaction.on_commit(_send)
    return 200, {'message': 'If your email is unverified, a new verification email has been sent.'}
```

Key: `resend-verification` always returns 200 with the same message regardless of whether the user exists or is already verified. This prevents email enumeration.

#### 5. `core/api.py` — Update registration to send emails

In the `register()` function, after `access_token = create_access_token(user)` (line 55), add email sends:

```python
def _send_registration_emails():
    token = generate_verification_token(user.id)
    verification_url = f'{settings.FRONTEND_URL}/verify-email?token={token}'
    user_name = user.full_name or user.email

    EmailService.send_email(
        to=user.email,
        subject='Verify your email — Monie',
        template_name='email/verify_email',
        context={'user_name': user_name, 'verification_url': verification_url},
    )
    EmailService.send_email(
        to=user.email,
        subject='Welcome to Monie!',
        template_name='email/welcome',
        context={'user_name': user_name},
    )

db_transaction.on_commit(_send_registration_emails)
```

Wait — the `register()` function uses `with transaction.atomic()` (line 39), not a method-level decorator. The `on_commit` callback should be registered inside the atomic block to be tied to that transaction. Move the registration inside the `with transaction.atomic()` block:

Actually, looking more carefully at the code: `create_access_token(user)` is called AFTER the atomic block (line 55 is after line 46 which closes the `with` block). So we need to register `on_commit` inside the atomic block. The callback will execute after the outer `atomic()` commits.

Better approach: register `on_commit` inside the `with transaction.atomic()` block, and keep the token generation inside the closure (it doesn't need the DB):

```python
with transaction.atomic():
    user = User.objects.create_user(...)
    WorkspaceService.create_workspace(...)
    UserService.record_consent(...)
    UserService.record_consent(...)

    def _send_registration_emails():
        token = generate_verification_token(user.id)
        verification_url = f'{settings.FRONTEND_URL}/verify-email?token={token}'
        user_name = user.full_name or user.email

        EmailService.send_email(
            to=user.email,
            subject='Verify your email — Monie',
            template_name='email/verify_email',
            context={'user_name': user_name, 'verification_url': verification_url},
        )
        EmailService.send_email(
            to=user.email,
            subject='Welcome to Monie!',
            template_name='email/welcome',
            context={'user_name': user_name},
        )

    db_transaction.on_commit(_send_registration_emails)

access_token = create_access_token(user)
```

#### 6. Email templates

**`templates/email/verify_email.html`** — extends `base.html`:
- Preheader: "Please verify your email address"
- Content: "Hi {{ user_name }}, please verify your email address to get the most out of Monie."
- CTA button: "Verify Email" → `{{ verification_url }}`
- Fallback: "If the button doesn't work, copy this link: {{ verification_url }}"

**`templates/email/verify_email.txt`** — extends `base.txt`:
- Plain text version with full URL

**`templates/email/welcome.html`** — extends `base.html`:
- Preheader: "Welcome to Monie!"
- Content: Welcome message, brief feature overview (track spending, set budgets, collaborate)
- CTA button: "Get Started" → `{{ frontend_url }}`

**`templates/email/welcome.txt`** — plain text version

#### 7. Tests — `core/tests/test_email_verification.py`

Test cases:
- `test_verify_email_success` — create user with `email_verified=False`, generate token, verify it, assert `email_verified=True`
- `test_verify_email_already_verified` — returns 400
- `test_verify_email_invalid_token` — returns 400
- `test_verify_email_expired_token` — returns 400 (mock TimestampSigner to expire)
- `test_resend_verification_sends_email` — unverified user, check `mail.outbox`
- `test_resend_verification_returns_same_message_for_unknown_email` — anti-enumeration check
- `test_resend_verification_rate_limited` — 3 requests in 1 hour
- `test_registration_sends_verification_and_welcome` — register user, check `mail.outbox` has 2 emails

### Done criteria
- [ ] `POST /api/auth/verify-email` works with valid token
- [ ] `POST /api/auth/resend-verification` sends email, rate-limited
- [ ] Registration sends both verification and welcome emails
- [ ] All email templates render without errors
- [ ] Anti-enumeration: resend always returns 200
- [ ] All tests pass

### Verification commands
```bash
cd backend
uv run ruff check --fix . && uv run ruff format .
pytest core/tests/test_email_verification.py -v
pytest core/tests/test_auth.py -v
```

---

## Task 5: Password Reset + Password Changed Emails

**Context budget: ~18k tokens**

### Goal
Implement forgot-password flow with email token, and send password-changed notification emails.

### Files to create
- `backend/templates/email/reset_password.html`
- `backend/templates/email/reset_password.txt`
- `backend/templates/email/password_changed.html`
- `backend/templates/email/password_changed.txt`
- `backend/core/tests/test_password_reset.py`

### Files to modify
- `backend/core/schemas/auth.py`
- `backend/core/schemas/__init__.py`
- `backend/core/api.py`
- `backend/users/services.py`
- `backend/workspaces/services.py`
- `backend/users/exceptions.py`

### Implementation details

#### 1. `core/schemas/auth.py` — New schemas

```python
class ForgotPasswordIn(BaseModel):
    email: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        validator = EmailValidator()
        try:
            validator(v)
        except DjangoValidationError:
            raise ValueError('Enter a valid email address')
        return v


class ResetPasswordIn(BaseModel):
    uidb64: str
    token: str
    new_password: str = Field(min_length=8, max_length=128)
```

Update `core/schemas/__init__.py` exports.

#### 2. `core/api.py` — New endpoints

Add imports:
```python
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
```

**Forgot password:**
```python
@router.post('/forgot-password', response={200: MessageOut, 429: DetailOut})
@rate_limit('forgot_password', limit=3, period=3600)
def forgot_password(request, data: ForgotPasswordIn):
    user = User.objects.filter(email=data.email).first()
    if not user:
        return 200, {'message': 'If an account exists with this email, a reset link has been sent.'}

    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = f'{settings.FRONTEND_URL}/reset-password?uid={uidb64}&token={token}'
    user_name = user.full_name or user.email

    def _send():
        EmailService.send_email(
            to=user.email,
            subject='Reset your password — Monie',
            template_name='email/reset_password',
            context={'user_name': user_name, 'reset_url': reset_url},
        )

    db_transaction.on_commit(_send)
    return 200, {'message': 'If an account exists with this email, a reset link has been sent.'}
```

**Reset password:**
```python
@router.post('/reset-password', response={200: MessageOut, 400: DetailOut})
def reset_password(request, data: ResetPasswordIn):
    try:
        uid = force_str(urlsafe_base64_decode(data.uidb64))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError):
        return 400, {'detail': 'Invalid reset link'}

    if not default_token_generator.check_token(user, data.token):
        return 400, {'detail': 'Invalid or expired reset link'}

    user.set_password(data.new_password)
    user.save(update_fields=['password'])

    user_name = user.full_name or user.email
    EmailService.send_email(
        to=user.email,
        subject='Your password was changed — Monie',
        template_name='email/password_changed',
        context={'user_name': user_name, 'changed_by_admin': False},
    )

    return 200, {'message': 'Password has been reset successfully'}
```

Note: No `on_commit` needed here — the `save()` is already committed, and `send_email` is fire-and-forget with `fail_silently` handled internally.

Actually, there's no transaction wrapping this endpoint, so `on_commit` would fire immediately anyway. Direct call is fine.

Key: `forgot-password` always returns 200 with the same message (anti-enumeration).

#### 3. `users/services.py` — Add password changed email to change_password

Add `@db_transaction.atomic` decorator and `on_commit` email:

```python
@staticmethod
@db_transaction.atomic
def change_password(user: User, current_password: str, new_password: str) -> None:
    if not user.check_password(current_password):
        raise UserInvalidPasswordError()

    user.set_password(new_password)
    user.save()

    def _notify():
        EmailService.send_email(
            to=user.email,
            subject='Your password was changed — Monie',
            template_name='email/password_changed',
            context={'user_name': user.full_name or user.email, 'changed_by_admin': False},
        )

    db_transaction.on_commit(_notify)
```

#### 4. `workspaces/services.py` — Add password changed email to admin reset

In `reset_password()` method, after `target_user.set_password(new_password)` and `target_user.save()`, add:

```python
from common.email import EmailService

target_user_email = target_user.email
target_user_name = target_user.full_name or target_user.email

def _notify():
    EmailService.send_email(
        to=target_user_email,
        subject='Your password was changed — Monie',
        template_name='email/password_changed',
        context={'user_name': target_user_name, 'changed_by_admin': True},
    )

db_transaction.on_commit(_notify)
```

#### 5. Email templates

**`templates/email/reset_password.html`** — extends `base.html`:
- Preheader: "Reset your Monie password"
- Content: "Hi {{ user_name }}, we received a request to reset your password. This link expires in 24 hours."
- CTA: "Reset Password" → `{{ reset_url }}`
- Note: "If you didn't request this, you can safely ignore this email."

**`templates/email/reset_password.txt`** — plain text version

**`templates/email/password_changed.html`** — extends `base.html`:
- Preheader: "Your Monie password was changed"
- Content: "Hi {{ user_name }}, your password was successfully changed."
- Conditional: "{% if changed_by_admin %}This was done by a workspace administrator.{% endif %}"
- Security note: "If you didn't make this change, contact support immediately."

**`templates/email/password_changed.txt`** — plain text version

#### 6. Tests — `core/tests/test_password_reset.py`

Test cases:
- `test_forgot_password_sends_email` — existing user, check mail.outbox
- `test_forgot_password_unknown_email_returns_200` — anti-enumeration
- `test_forgot_password_rate_limited` — 3 per hour
- `test_reset_password_success` — generate valid uid+token, reset, verify new password works
- `test_reset_password_invalid_uid` — returns 400
- `test_reset_password_invalid_token` — returns 400
- `test_reset_password_token_single_use` — reuse token, returns 400
- `test_change_password_sends_notification` — self-service change
- `test_admin_reset_password_sends_notification` — admin resets member password

### Done criteria
- [ ] `POST /api/auth/forgot-password` sends reset email, always returns 200
- [ ] `POST /api/auth/reset-password` works with valid uid+token
- [ ] Password reset tokens are one-time-use
- [ ] Password changed emails sent for self-change and admin-reset
- [ ] All email templates render
- [ ] Rate limiting works on forgot-password
- [ ] All tests pass

### Verification commands
```bash
cd backend
uv run ruff check --fix . && uv run ruff format .
pytest core/tests/test_password_reset.py -v
pytest users/tests/ -v
```

---

## Task 6: Email Change Flow

**Context budget: ~18k tokens**

### Goal
Allow users to change their email with verification to the new address and notification to the old address.

### Files to create
- `backend/templates/email/email_change_verify.html`
- `backend/templates/email/email_change_verify.txt`
- `backend/templates/email/email_change_notify.html`
- `backend/templates/email/email_change_notify.txt`
- `backend/core/tests/test_email_change.py`

### Files to modify
- `backend/core/schemas/auth.py`
- `backend/core/schemas/__init__.py`
- `backend/core/api.py`
- `backend/users/exceptions.py`

### Implementation details

Note: `common/tokens.py` already has `generate_email_change_token` and `verify_email_change_token` (created in Task 4).

#### 1. `core/schemas/auth.py` — New schemas

```python
class EmailChangeRequestIn(BaseModel):
    password: str
    new_email: str

    @field_validator('new_email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        validator = EmailValidator()
        try:
            validator(v)
        except DjangoValidationError:
            raise ValueError('Enter a valid email address')
        return v


class EmailChangeConfirmIn(BaseModel):
    token: str
```

Update `core/schemas/__init__.py` exports.

#### 2. `users/exceptions.py` — New exceptions

```python
class UserEmailAlreadyInUseError(ValidationError):
    default_message = 'This email is already in use'


class UserInvalidEmailChangeTokenError(ValidationError):
    default_message = 'Invalid or expired email change token'


class UserSameEmailError(ValidationError):
    default_message = 'New email must be different from current email'
```

#### 3. `core/api.py` — New endpoints

Both endpoints require authentication via `JWTAuth`.

**Request email change:**
```python
@router.post('/request-email-change', response={200: MessageOut, 400: DetailOut}, auth=JWTAuth())
def request_email_change(request, data: EmailChangeRequestIn):
    user = request.auth

    if not user.check_password(data.password):
        return 400, {'detail': 'Invalid password'}

    if data.new_email.lower() == user.email.lower():
        return 400, {'detail': 'New email must be different from current email'}

    if User.objects.filter(email__iexact=data.new_email).exists():
        return 400, {'detail': 'This email is already in use'}

    user.pending_email = data.new_email
    user.save(update_fields=['pending_email'])

    token = generate_email_change_token(user.id, data.new_email)
    confirm_url = f'{settings.FRONTEND_URL}/confirm-email-change?token={token}'

    def _send():
        EmailService.send_email(
            to=data.new_email,
            subject='Confirm your new email — Monie',
            template_name='email/email_change_verify',
            context={
                'user_name': user.full_name or user.email,
                'confirm_url': confirm_url,
                'new_email': data.new_email,
            },
        )

    db_transaction.on_commit(_send)
    return 200, {'message': 'Verification email sent to your new address'}
```

**Confirm email change:**
```python
@router.post('/confirm-email-change', response={200: MessageOut, 400: DetailOut}, auth=JWTAuth())
def confirm_email_change(request, data: EmailChangeConfirmIn):
    result = verify_email_change_token(data.token)
    if not result:
        return 400, {'detail': 'Invalid or expired token'}

    user_id, new_email = result
    user = request.auth

    if user.id != user_id:
        return 400, {'detail': 'Invalid token'}

    if user.pending_email != new_email:
        return 400, {'detail': 'This email change request is no longer valid'}

    if User.objects.filter(email__iexact=new_email).exclude(id=user.id).exists():
        return 400, {'detail': 'This email is already in use'}

    old_email = user.email
    user.email = new_email
    user.pending_email = ''
    user.email_verified = True
    user.save(update_fields=['email', 'pending_email', 'email_verified'])

    def _notify_old():
        EmailService.send_email(
            to=old_email,
            subject='Your email was changed — Monie',
            template_name='email/email_change_notify',
            context={
                'user_name': user.full_name or new_email,
                'old_email': old_email,
                'new_email': new_email,
            },
        )

    db_transaction.on_commit(_notify_old)
    return 200, {'message': 'Email changed successfully'}
```

Important: `confirm-email-change` requires `JWTAuth()`. The token encodes user_id and we verify it matches the authenticated user. The JWT still has the old email, but the auth system uses `user_id` from the token and fetches the user from DB — so the next request will use the updated email.

#### 4. Email templates

**`templates/email/email_change_verify.html`**:
- Preheader: "Confirm your new email address"
- Content: "Hi {{ user_name }}, please confirm that {{ new_email }} is your new email address."
- CTA: "Confirm Email Change" → `{{ confirm_url }}`

**`templates/email/email_change_notify.html`**:
- Preheader: "Your Monie email was changed"
- Content: "Hi {{ user_name }}, your Monie email was changed from {{ old_email }} to {{ new_email }}."
- Security note: "If you didn't make this change, contact support immediately."

#### 5. Tests — `core/tests/test_email_change.py`

Test cases:
- `test_request_email_change_sends_verification` — check email sent to new address
- `test_request_email_change_wrong_password` — returns 400
- `test_request_email_change_same_email` — returns 400
- `test_request_email_change_email_in_use` — returns 400
- `test_confirm_email_change_success` — email changes, old email notified
- `test_confirm_email_change_invalid_token` — returns 400
- `test_confirm_email_change_wrong_user` — returns 400
- `test_confirm_email_change_pending_email_mismatch` — returns 400
- `test_confirm_email_change_email_now_taken` — race condition protection

### Done criteria
- [ ] `POST /api/auth/request-email-change` verifies password, sends to new email
- [ ] `POST /api/auth/confirm-email-change` swaps email, notifies old address
- [ ] `pending_email` field used correctly
- [ ] Old email receives notification
- [ ] Race condition handled: email taken between request and confirm
- [ ] Both endpoints require authentication
- [ ] All tests pass

### Verification commands
```bash
cd backend
uv run ruff check --fix . && uv run ruff format .
pytest core/tests/test_email_change.py -v
```

---

## Task 7: Workspace Invitation Emails

**Context budget: ~12k tokens**

### Goal
Send invitation emails when admins add members to a workspace.

### Files to create
- `backend/templates/email/workspace_invitation_new.html`
- `backend/templates/email/workspace_invitation_new.txt`
- `backend/templates/email/workspace_invitation_existing.html`
- `backend/templates/email/workspace_invitation_existing.txt`
- `backend/workspaces/tests/test_invitation_emails.py`

### Files to modify
- `backend/workspaces/services.py`

### Implementation details

#### 1. `workspaces/services.py` — Update `add_member()`

Add `from common.email import EmailService` import.

At the end of the **existing_user branch** (before the return), capture workspace name and add email:
```python
workspace = Workspace.objects.get(id=workspace_id)
admin_name = user.full_name or user.email

def _send_existing():
    EmailService.send_email(
        to=existing_user.email,
        subject=f'You were added to {workspace.name} — Monie',
        template_name='email/workspace_invitation_existing',
        context={
            'user_name': existing_user.full_name or existing_user.email,
            'workspace_name': workspace.name,
            'admin_name': admin_name,
            'role': data.role,
            'frontend_url': settings.FRONTEND_URL,
        },
    )
db_transaction.on_commit(_send_existing)
```

At the end of the **new_user branch** (before the return), add email:
```python
def _send_new():
    EmailService.send_email(
        to=new_user.email,
        subject=f'You were invited to {workspace.name} — Monie',
        template_name='email/workspace_invitation_new',
        context={
            'user_name': new_user.full_name or new_user.email,
            'workspace_name': workspace.name,
            'admin_name': admin_name,
            'role': data.role,
            'email': new_user.email,
            'frontend_url': settings.FRONTEND_URL,
        },
    )
db_transaction.on_commit(_send_new)
```

Important: For new users, do NOT include the password in the email. The admin should share it via a separate secure channel.

Note: `Workspace.objects.get(id=workspace_id)` was already called at line 209 with `select_for_update()`, so we have the workspace. However, we need to capture the workspace name before leaving the method. We can store it from the existing queryset call.

Actually, looking at the code more carefully: line 209 does `Workspace.objects.select_for_update().get(id=workspace_id)` but doesn't store it. We should capture it:
```python
workspace = Workspace.objects.select_for_update().get(id=workspace_id)
```
Then use `workspace` for both the existing check and the email.

#### 2. Email templates

**`templates/email/workspace_invitation_new.html`**:
- Preheader: "You've been invited to join {{ workspace_name }}"
- Content: "Hi {{ user_name }}, {{ admin_name }} created a Monie account for you and added you as a {{ role }} to {{ workspace_name }}."
- Info: "Your login email is {{ email }}. Please ask {{ admin_name }} for your temporary password."
- CTA: "Sign In" → `{{ frontend_url }}/login`

**`templates/email/workspace_invitation_existing.html`**:
- Preheader: "You were added to {{ workspace_name }}"
- Content: "Hi {{ user_name }}, {{ admin_name }} added you as a {{ role }} to {{ workspace_name }}."
- CTA: "Open Monie" → `{{ frontend_url }}`

#### 3. Tests — `workspaces/tests/test_invitation_emails.py`

Test cases:
- `test_add_new_user_sends_invitation_email` — check mail.outbox for correct template and recipient
- `test_add_existing_user_sends_invitation_email` — check mail.outbox
- `test_invitation_email_contains_workspace_name` — check email body/subject
- `test_invitation_email_does_not_contain_password` — security check

### Done criteria
- [ ] New users receive invitation email with workspace info
- [ ] Existing users receive notification email
- [ ] Password is NOT included in the email
- [ ] Both HTML and plain text versions work
- [ ] All tests pass

### Verification commands
```bash
cd backend
uv run ruff check --fix . && uv run ruff format .
pytest workspaces/tests/test_invitation_emails.py -v
```

---

## Task 8: Workspace Event Notification Emails

**Context budget: ~15k tokens**

### Goal
Send notification emails for workspace events: member removed, member left, workspace deleted, role changed.

### Files to create
- `backend/templates/email/member_removed.html` / `.txt`
- `backend/templates/email/member_left.html` / `.txt`
- `backend/templates/email/workspace_deleted.html` / `.txt`
- `backend/templates/email/role_changed.html` / `.txt`
- `backend/workspaces/tests/test_event_emails.py`

### Files to modify
- `backend/workspaces/services.py`

### Implementation details

#### 1. `workspaces/services.py` — `remove_member()` — Send to removed user

Before `member.delete()` (line 377), capture user info. After deletion logic, add `on_commit`:

```python
removed_user = User.objects.filter(id=member_user_id).first()
removed_user_email = removed_user.email if removed_user else None
removed_user_name = removed_user.full_name or removed_user.email if removed_user else ''
workspace = Workspace.objects.get(id=workspace_id)
admin_name = user.full_name or user.email

# ... existing deletion and workspace switch logic ...

def _notify():
    if removed_user_email:
        EmailService.send_email(
            to=removed_user_email,
            subject=f'You were removed from {workspace.name} — Monie',
            template_name='email/member_removed',
            context={
                'user_name': removed_user_name,
                'workspace_name': workspace.name,
                'admin_name': admin_name,
            },
        )
db_transaction.on_commit(_notify)
```

#### 2. `workspaces/services.py` — `leave()` — Send to all admins/owners

After `member.delete()` and workspace switch logic, add:

```python
workspace = Workspace.objects.get(id=workspace_id)
leaver_name = user.full_name or user.email
leaver_id = user.id

admins = User.objects.filter(
    workspace_memberships__workspace_id=workspace_id,
    workspace_memberships__role__in=[Role.OWNER, Role.ADMIN],
).exclude(id=leaver_id)

for admin in admins:
    admin_email = admin.email
    admin_name = admin.full_name or admin.email
    ws_name = workspace.name

    def _make_notify(a_email, a_name, w_name):
        def _notify():
            EmailService.send_email(
                to=a_email,
                subject=f'{leaver_name} left {w_name} — Monie',
                template_name='email/member_left',
                context={
                    'user_name': a_name,
                    'leaver_name': leaver_name,
                    'workspace_name': w_name,
                    'frontend_url': settings.FRONTEND_URL,
                },
            )
        return _notify
    db_transaction.on_commit(_make_notify(admin_email, admin_name, ws_name))
```

#### 3. `workspaces/services.py` — `update_role()` — Send to affected member

After `member.save()` (line 336), add:

```python
workspace = Workspace.objects.get(id=workspace_id)
target_user = User.objects.get(id=member_user_id)
admin_name = user.full_name or user.email

def _notify():
    EmailService.send_email(
        to=target_user.email,
        subject=f'Your role was changed in {workspace.name} — Monie',
        template_name='email/role_changed',
        context={
            'user_name': target_user.full_name or target_user.email,
            'workspace_name': workspace.name,
            'old_role': old_role,
            'new_role': new_role,
            'admin_name': admin_name,
        },
    )
db_transaction.on_commit(_notify)
```

#### 4. `workspaces/services.py` — `WorkspaceService.delete_workspace()` — Send to all other members

After gathering `affected_users` (line ~225), capture workspace name and send emails. Do this BEFORE `workspace.delete()`:

```python
workspace_name = workspace.name
deleter_name = user.full_name or user.email

for affected_user in affected_users:
    au_email = affected_user.email
    au_name = affected_user.full_name or au_email

    def _make_notify(email, name, ws_name, d_name):
        def _notify():
            EmailService.send_email(
                to=email,
                subject=f'{ws_name} was deleted — Monie',
                template_name='email/workspace_deleted',
                context={
                    'user_name': name,
                    'workspace_name': ws_name,
                    'deleter_name': d_name,
                },
            )
        return _notify
    db_transaction.on_commit(_make_notify(au_email, au_name, workspace_name, deleter_name))
```

#### 5. Email templates

**`member_removed.html`**: "You were removed from {{ workspace_name }}" by {{ admin_name }}. "If you believe this was a mistake, please contact the workspace administrator."

**`member_left.html`**: "{{ leaver_name }} left {{ workspace_name }}". "You may want to review your workspace members."

**`workspace_deleted.html`**: "{{ workspace_name }} was deleted by {{ deleter_name }}". "All data associated with this workspace has been permanently removed."

**`role_changed.html`**: "Your role in {{ workspace_name }} was changed from {{ old_role }} to {{ new_role }} by {{ admin_name }}."

Each has corresponding `.txt` file.

#### 6. Tests — `workspaces/tests/test_event_emails.py`

Test cases:
- `test_remove_member_sends_email` — removed user gets email
- `test_remove_member_email_has_workspace_name` — verify subject/body content
- `test_leave_sends_admin_notifications` — all admins/owners get email
- `test_leave_does_not_notify_leaver` — leaver doesn't get notified
- `test_leave_does_not_notify_viewers` — only admins/owners
- `test_delete_workspace_sends_member_notifications` — all affected members get email
- `test_delete_workspace_deleter_not_notified` — owner doing the delete doesn't get email
- `test_update_role_sends_email` — affected member gets email with old/new role
- `test_update_role_admin_not_notified` — admin making the change doesn't get email

### Done criteria
- [ ] Removed members receive notification email
- [ ] Admins receive notification when a member leaves
- [ ] All members receive notification when workspace is deleted
- [ ] Members receive notification when their role changes
- [ ] Workspace name captured before deletion
- [ ] No notification sent to the person performing the action
- [ ] All tests pass

### Verification commands
```bash
cd backend
uv run ruff check --fix . && uv run ruff format .
pytest workspaces/tests/test_event_emails.py -v
```

---

## Task 9: Frontend — Password Reset Pages

**Context budget: ~15k tokens**

### Goal
Create forgot-password and reset-password pages on the frontend.

### Files to create
- `frontend/src/pages/ForgotPasswordPage.tsx`
- `frontend/src/pages/ResetPasswordPage.tsx`

### Files to modify
- `frontend/src/api/client.ts`
- `frontend/src/App.tsx`

### Implementation details

#### 1. `api/client.ts` — New methods in `authApi`

```typescript
forgotPassword: (email: string) =>
    api.post('/auth/forgot-password', { email }),

resetPassword: (uidb64: string, token: string, new_password: string) =>
    api.post('/auth/reset-password', { uidb64, token, new_password }),
```

#### 2. `App.tsx` — New routes

Add to public routes (no auth required):
```tsx
<Route path="/forgot-password" element={<ForgotPasswordPage />} />
<Route path="/reset-password" element={<ResetPasswordPage />} />
```

#### 3. `ForgotPasswordPage.tsx`

- Simple form with email input + submit button
- Calls `authApi.forgotPassword(email)`
- Always shows success message: "If an account exists with this email, a reset link has been sent."
- Link back to login page: "Back to login"
- Style matches existing `Login.tsx` page (same card layout, input styling, button)
- Loading state on submit button

#### 4. `ResetPasswordPage.tsx`

- Reads `uid` and `token` from URL query params (`useSearchParams`)
- Form with new password + confirm password fields
- Client-side validation: passwords match, min 8 characters
- Calls `authApi.resetPassword(uid, token, newPassword)`
- On success: shows "Password reset successfully" with link to login
- On error: shows error message with link to forgot-password page
- Invalid/expired token: shows "This reset link is invalid or has expired"

### Reference files to read first
- `frontend/src/pages/Login.tsx` — for styling patterns
- `frontend/src/pages/Register.tsx` — for form handling patterns

### Done criteria
- [ ] `/forgot-password` page renders and calls API
- [ ] `/reset-password` page reads uid+token from URL
- [ ] Both pages match existing auth page styling
- [ ] Form validation works (email format, password length, passwords match)
- [ ] Success/error states handled correctly
- [ ] `npm run lint` passes

### Verification commands
```bash
cd frontend
npm run lint
npm run build
```

---

## Task 10: Frontend — Email Verification & Change Pages

**Context budget: ~15k tokens**

### Goal
Create email verification page and email change flow in settings.

### Files to create
- `frontend/src/pages/VerifyEmailPage.tsx`
- `frontend/src/pages/ConfirmEmailChangePage.tsx`
- `frontend/src/components/profile/EmailVerificationBadge.tsx`

### Files to modify
- `frontend/src/api/client.ts`
- `frontend/src/App.tsx`
- `frontend/src/components/profile/EditProfileForm.tsx`
- `frontend/src/pages/ProfilePage.tsx`

### Implementation details

#### 1. `api/client.ts` — New methods in `authApi`

```typescript
verifyEmail: (token: string) =>
    api.post('/auth/verify-email', { token }),

resendVerification: (email: string) =>
    api.post('/auth/resend-verification', { email }),

requestEmailChange: (password: string, newEmail: string) =>
    api.post('/auth/request-email-change', { password, new_email: newEmail }),

confirmEmailChange: (token: string) =>
    api.post('/auth/confirm-email-change', { token }),
```

#### 2. `App.tsx` — New routes

Add to routes:
```tsx
<Route path="/verify-email" element={<VerifyEmailPage />} />
<Route path="/confirm-email-change" element={<ConfirmEmailChangePage />} />
```

`/verify-email` is public (no auth — the user may not be logged in when clicking the link).
`/confirm-email-change` needs auth (wrapped in `ProtectedRoute`).

#### 3. `VerifyEmailPage.tsx`

- Reads `token` from URL query params on mount (`useSearchParams`)
- Calls `authApi.verifyEmail(token)` automatically via `useEffect`
- Shows three states: loading spinner → success / error
- Success: "Email verified! You can now close this page." with link to dashboard
- Error: "Invalid or expired link" with option to resend verification email
- Resend form: email input → `authApi.resendVerification(email)` → success message

#### 4. `ConfirmEmailChangePage.tsx`

- Requires authentication (inside `ProtectedRoute`)
- Reads `token` from URL query params
- Calls `authApi.confirmEmailChange(token)` automatically
- Shows loading → success/error
- Success: "Email changed successfully" — updates auth context user data
- Error: "Invalid or expired link" with link to settings

#### 5. `EmailVerificationBadge.tsx`

Small reusable component:
- Props: `verified: boolean`, `email: string`, `onResend?: () => void`
- If `verified`: green checkmark icon + "Verified" text
- If not verified: yellow warning icon + "Not verified" + "Resend" button
- "Resend" calls `authApi.resendVerification(email)` and shows toast

#### 6. `EditProfileForm.tsx` — Replace email input with read-only + change flow

Currently allows editing email directly. Change to:
- Show current email as **read-only text** (not an input)
- Show `EmailVerificationBadge` next to the email
- Add "Change Email" button that reveals an inline form:
  - New email input
  - Current password input
  - Submit → calls `authApi.requestEmailChange(password, newEmail)`
  - Success: toast "Check your new email for confirmation", hide the form

#### 7. `ProfilePage.tsx`

Pass `email_verified` from the user object (now in `UserOut` from backend) to `EditProfileForm`.

### Reference files to read first
- `frontend/src/components/profile/EditProfileForm.tsx`
- `frontend/src/pages/ProfilePage.tsx`
- `frontend/src/contexts/AuthContext.tsx` — for `updateUser()`

### Done criteria
- [ ] `/verify-email?token=...` auto-verifies and shows result
- [ ] `/confirm-email-change?token=...` confirms email change
- [ ] Profile page shows email as read-only with verification badge
- [ ] "Change Email" flow works (password + new email → confirmation email)
- [ ] Resend verification button works
- [ ] `npm run lint` passes

### Verification commands
```bash
cd frontend
npm run lint
npm run build
```

---

## Task 11: Integration Tests & Cleanup

**Context budget: ~12k tokens**

### Goal
Run full test suite, fix any issues, ensure everything works end-to-end.

### Tasks

1. **Run full backend test suite**
   ```bash
   cd backend && pytest -v
   ```

2. **Verify all email flows work with locmem backend**
   - All tests that send email should use `mail.outbox` (Django's test email backend)
   - Verify no emails leak between tests
   - Each test class should clear `mail.outbox` in `setUp` if needed

3. **Check `config/test_settings.py`** — ensure `EMAIL_BACKEND` is `locmem.EmailBackend` (should already be set)

4. **Run full frontend build**
   ```bash
   cd frontend && npm run lint && npm run build
   ```

5. **Check for missing imports** across all new/modified files

6. **Update `AGENTS.md`** — add a section about email patterns:
   - How to send email: `EmailService.send_email()` with `db_transaction.on_commit()`
   - How to add new email templates (create .html + .txt, extend base)
   - Token patterns: `TimestampSigner` for verification, `PasswordResetTokenGenerator` for reset
   - Anti-enumeration pattern: always return 200 for forgot-password and resend-verification

7. **Verify `example.env`** has all new environment variables documented

8. **Fix any test failures** from previous tasks

### Done criteria
- [ ] `pytest` — all tests pass, zero failures
- [ ] `npm run lint` — no errors
- [ ] `npm run build` — builds successfully
- [ ] No missing imports or undefined references
- [ ] AGENTS.md updated with email patterns section
- [ ] `example.env` complete

### Verification commands
```bash
cd backend && pytest -v
cd frontend && npm run lint && npm run build
```

---

## Agent Prompt Template

```
## Task Assignment

**TASK_NUMBER = [X]**

You are implementing a task from the email backend implementation plan.

## Your Task

1. Read the implementation plan at `.ipm/IMPLEMENTATION_PLAN.md`
2. Find Task {TASK_NUMBER} and understand what needs to be done
3. Read all files mentioned in the task's "Files to modify" / "Files to create" sections
4. Read AGENTS.md for coding conventions
5. Implement the changes as specified
6. Run the verification commands listed in the task
7. Ensure all "Done criteria" are satisfied

## Important Rules

- Follow the AGENTS.md coding guidelines
- Backend: run `uv run ruff check --fix .` and `uv run ruff format .` after changes
- Backend: run relevant tests after changes
- Frontend: run `npm run lint` after changes
- Do NOT commit changes unless explicitly asked
- When done, update the Progress Tracker in `.ipm/IMPLEMENTATION_PLAN.md` (check the box)

## Context

This is part of adding email functionality to the Monie backend. The system uses:
- Direct SMTP (Google/ProtonMail) configured via environment variables
- `common/email.py` EmailService for sending (HTML + plain text)
- `common/tokens.py` for stateless verification tokens (TimestampSigner)
- `db_transaction.on_commit()` for non-blocking email sends
- Django templates in `backend/templates/email/` for HTML+plain text
- Django's `PasswordResetTokenGenerator` for password reset tokens
- Anti-enumeration: forgot-password and resend-verification always return 200

Work on ONLY Task {TASK_NUMBER}. Do not modify files outside the task's scope.
```
