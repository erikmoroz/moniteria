# Coding Summaries

## Fix #2: GDPR — Add UserTwoFactor to export_all_data

**Files changed:**
- `backend/users/services.py` — Added `UserTwoFactor` import and `two_factor_data` section to `UserService.export_all_data()` exporting `is_enabled`, `last_used_at`, and `created_at` (no secrets). Added `two_factor` key to the return dict. Renumbered subsequent comment sections (Consents → 4, Workspace → 5).
- `backend/users/tests/test_two_factor.py` — Added `TestTwoFAExport` class with two tests: `test_export_includes_2fa_when_not_configured` (verifies defaults when no 2FA record exists) and `test_export_includes_2fa_when_enabled` (verifies 2FA fields appear and secrets are excluded from export).

## Fix #3: Handle pending 2FA records in admin_reset

**Files changed:**
- `backend/users/exceptions.py` — Added `TwoFactorNotEnabledError` exception (extends `NotFoundError`, 404) with message "Two-factor authentication is not enabled for this user" and code `two_factor_not_enabled`.
- `backend/users/two_factor.py` — Imported `TwoFactorNotEnabledError`. Updated `TwoFactorService.admin_reset` to check `not twofa.is_enabled` in addition to `not twofa`, so pending-setup records (`is_enabled=False`) raise the error instead of being silently deleted.
- `backend/users/tests/test_two_factor.py` — Added `test_reset_when_2fa_pending_setup` to `TestAdminReset2FA`: creates a pending 2FA setup record via `TwoFactorService.setup()`, then asserts `admin_reset` returns 404.

## Fix #5: Test cleanup — move inline imports to top level

**Files changed:**
- `backend/users/tests/test_two_factor.py` — Added `Client` to the top-level import `from django.test import Client, TestCase`. Removed 23 inline `from django.test import Client` statements (and trailing blank lines) from inside individual test methods across all test classes (`TestTwoFASetup`, `TestTwoFADisable`, `TestTwoFAStatus`, `TestTwoFARegenerateCodes`, `TestAdminReset2FA`, `TestVerify2FAEndpoint`).

## Fix #4: Improve verify-2fa error when 2FA disabled mid-flow

**Files changed:**
- `backend/core/api.py` — Added `TwoFactorNotEnabledError` import and `404: DetailOut` to the `/verify-2fa` response schema. Added a check after fetching the user (before verifying the code) that raises `TwoFactorNotEnabledError` if the 2FA record is missing or not enabled. This provides a meaningful 404 error instead of a misleading "Invalid verification code" (401) when an admin resets 2FA between `/login` and `/verify-2fa`.
- `backend/users/tests/test_two_factor.py` — Added `TestVerify2FAEndpoint` class with `test_verify_2fa_returns_404_when_2fa_disabled_mid_flow`: enables 2FA, logs in to obtain a temp token, disables 2FA via `TwoFactorService.disable()`, then calls `/verify-2fa` and asserts a 404 with "not enabled" in the response detail.
