# GDPR Compliance Documentation

This directory contains documentation for Monie's GDPR compliance implementation.

## Documents

| Document | Description |
|----------|-------------|
| [Data Processing Records](./data-processing-records.md) | Article 30 records of processing activities |
| [Breach Notification Process](./breach-notification-process.md) | Articles 33/34 incident response procedures |
| Privacy Policy | Available at `/privacy` in the application |
| Terms of Service | Available at `/terms` in the application |

## Technical Implementation

### Consent Management (Articles 6, 7)

- **Model:** `UserConsent` in `backend/users/models.py`
- **Service:** `UserService.record_consent`, `withdraw_consent`, `get_active_consents` in `backend/users/services.py`
- **Endpoints:**
  - `GET /api/users/me/consents` — list active consents
  - `POST /api/users/me/consents` — grant consent
  - `DELETE /api/users/me/consents/{type}` — withdraw consent
- **Registration:** Consent is recorded during user registration (`backend/core/api.py`)
- **Frontend:** Checkbox on `/register` page requiring acceptance before account creation

### Right to Erasure (Article 17)

- **Service:** `UserService.delete_account` in `backend/users/services.py`
- **Endpoints:**
  - `GET /api/users/me/deletion-check` — pre-deletion impact summary
  - `DELETE /api/users/me` — permanently delete account (requires password)
- **Frontend:** Delete Account section in Profile Settings → Account tab
- **Cascade behavior:**
  - Solo-owned workspaces: fully deleted with all budget data
  - Shared workspace memberships: membership removed, workspace data preserved
  - `created_by`/`updated_by` on financial records: set to NULL (anonymized)

### Right to Access & Portability (Articles 15, 20)

- **Service:** `UserService.export_all_data` in `backend/users/services.py`
- **Endpoint:** `GET /api/users/me/export` — downloads JSON file with all personal data
- **Rate limit:** 3 exports per hour
- **Frontend:** Export button in Profile Settings → Account tab
- **Includes:** Profile, preferences, consents, all workspace/budget/transaction data

### Public-Facing Pages

- `/privacy` — Privacy Policy
- `/terms` — Terms of Service

## Data Subject Rights Summary

| Right | Implementation |
|-------|---------------|
| Access (Art. 15) | `/api/users/me/export` |
| Rectification (Art. 16) | `/api/users/me` (PATCH) |
| Erasure (Art. 17) | `/api/users/me` (DELETE) |
| Portability (Art. 20) | `/api/users/me/export` (JSON download) |
| Withdraw Consent (Art. 7) | `/api/users/me/consents/{type}` (DELETE) |
