# Coding Preferences & Learnings

Summary of style decisions and corrections captured during implementation. Use these as examples of preferred patterns.

---

## Service Methods: No Nested Functions

**Source:** Task 7 — Workspace Invitation Emails

**Feedback:** Do not use nested functions inside service methods. Move them to class-level static methods instead.

### Bad

```python
class WorkspaceMemberService:
    @staticmethod
    @db_transaction.atomic
    def add_member(user, workspace_id, data):
        workspace = Workspace.objects.select_for_update().get(id=workspace_id)
        # ...
        admin_name = user.full_name or user.email

        def _send_existing():
            EmailService.send_email(
                to=existing_user.email,
                subject=f'You were added to {workspace.name} — Monie',
                template_name='email/workspace_invitation_existing',
                context={...},
            )

        db_transaction.on_commit(_send_existing)
```

### Good

```python
class WorkspaceMemberService:
    @staticmethod
    @db_transaction.atomic
    def add_member(user, workspace_id, data):
        workspace = Workspace.objects.select_for_update().get(id=workspace_id)
        # ...
        admin_name = user.full_name or user.email
        db_transaction.on_commit(
            lambda: WorkspaceMemberService._send_existing_user_email(
                existing_user, workspace, admin_name, data.role
            )
        )

    @staticmethod
    def _send_existing_user_email(existing_user, workspace, admin_name, role):
        EmailService.send_email(
            to=existing_user.email,
            subject=f'You were added to {workspace.name} — Monie',
            template_name='email/workspace_invitation_existing',
            context={...},
        )
```

**Rule:** Helper logic that would be a nested function belongs as a private static method on the service class. Use a `lambda` in `on_commit` to call it.

---

## Tests: Use Factory Classes, Not Service Calls

**Source:** Task 8 — Workspace Event Notification Emails

**Feedback:** When setting up test data, use factory classes (`WorkspaceFactory`, `WorkspaceMemberFactory`, `UserFactory`) instead of service methods (`WorkspaceService.create_workspace`). Service calls create extra side effects (e.g. additional owner memberships, currencies, budget accounts) that make test assertions unreliable.

### Bad

```python
owner = UserFactory(full_name='Owner')
workspace = WorkspaceService.create_workspace(user=owner, name='Team')
# This creates a real workspace with currencies, budget accounts, etc.
# and registers owner as the workspace owner via service logic.
```

### Good

```python
workspace = WorkspaceFactory(name='Team')
owner = UserFactory(full_name='Owner', current_workspace=workspace)
WorkspaceMemberFactory(workspace=workspace, user=owner, role='owner')
# Explicit, minimal setup — only the records needed for the test.
```

**Rule:** Prefer factories for test setup. Only use service calls when the test specifically validates service-level behavior (e.g. `test_delete_workspace_*` which calls `WorkspaceService.delete_workspace` directly).

---

## Loops with on_commit: Use Lambda Default Args

**Source:** Task 8 — Workspace Event Notification Emails

**Feedback:** When registering `on_commit` callbacks inside a loop, use lambda default arguments to capture loop variables by value. Without this, all callbacks reference the final loop iteration's values (late binding).

### Bad

```python
for admin in admins:
    db_transaction.on_commit(
        lambda: send_email(admin.email, admin.full_name)  # late binding!
    )
```

### Good

```python
for admin in admins:
    admin_email = admin.email
    admin_name = admin.full_name or admin.email
    db_transaction.on_commit(
        lambda e=admin_email, n=admin_name: send_email(e, n)
    )
```

**Rule:** Always capture loop variables via lambda default arguments (`lambda x=val: ...`) when registering `on_commit` callbacks in loops.

---

## Frontend: Token-Based Verification Pages

**Source:** Task 10 — Frontend Email Verification & Change Pages

**Pattern:** Pages that verify tokens from URL query params follow a consistent state machine pattern using `useEffect` + `useSearchParams`.

### Structure

```tsx
type State = 'loading' | 'success' | 'error'

export default function VerifyPage() {
  const [searchParams] = useSearchParams()
  const [state, setState] = useState<State>('loading')

  useEffect(() => {
    const token = searchParams.get('token')
    if (!token) {
      setState('error')
      return
    }
    authApi.verify(token)
      .then(() => setState('success'))
      .catch(() => setState('error'))
  }, [searchParams])

  // Render based on state
}
```

**Rules:**
- Always handle the missing-token case (`if (!token)` → error state)
- Public verification pages (email verify) are placed outside `ProtectedRoute`; authenticated pages (email change confirm) are wrapped in `ProtectedRoute`
- Success states should offer a navigation link; error states should offer a retry or resend option
- Anti-enumeration: resend endpoints always return success regardless of whether the email exists

---

## Frontend: Read-Only Fields with Inline Change Forms

**Source:** Task 10 — Frontend Email Verification & Change Pages

**Pattern:** When a field (like email) can no longer be edited directly but requires a separate flow, show it as read-only text with an inline expandable form.

### Structure

```tsx
// Read-only display + badge
<span className="...">{user.email}</span>
<button onClick={() => setShowChangeEmail(true)}>Change Email</button>

// Expandable inline form
{showChangeEmail && (
  <div className="mt-3 p-4 bg-surface-container-highest rounded-lg space-y-3">
    <input placeholder="New email address" />
    <input type="password" placeholder="Current password" />
    <div className="flex gap-2">
      <button onClick={handleChangeEmail}>Confirm</button>
      <button onClick={handleCancel}>Cancel</button>
    </div>
  </div>
)}
```

**Rules:**
- Show the current value as non-editable text (not a disabled input)
- Use a toggle button to reveal the inline form
- Cancel button resets all form state and hides the form
- The inline form calls a dedicated API endpoint (not the general profile update)
