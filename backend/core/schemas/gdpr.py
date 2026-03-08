"""GDPR-related schemas for account deletion and data portability."""

from pydantic import BaseModel


class AccountDeleteIn(BaseModel):
    """Input for account deletion — requires password confirmation."""

    password: str


class AccountDeleteCheckOut(BaseModel):
    """Pre-deletion check showing what will be affected."""

    can_delete: bool
    blocking_workspaces: list[dict] | None = None  # [{'id': 1, 'name': 'X', 'member_count': 3}]
    solo_workspaces: list[str]  # workspace names that will be deleted
    shared_workspace_memberships: int  # count of non-owned workspace memberships
    total_transactions: int  # count of transactions created by user
    total_planned_transactions: int
    total_currency_exchanges: int


class AccountDeleteOut(BaseModel):
    """Output confirming account deletion."""

    message: str
    deleted_workspaces: list[str]
