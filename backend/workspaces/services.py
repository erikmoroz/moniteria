"""Business logic for the workspaces app."""

from django.db import transaction as db_transaction
from django.db.models import Count, Min

from budget_accounts.models import BudgetAccount
from workspaces.demo_fixtures import create_demo_fixtures
from workspaces.exceptions import (
    CurrencyDuplicateSymbolError,
    CurrencyNotFoundError,
    WorkspaceCannotBeDeletedError,
)
from workspaces.models import Currency, Role, Workspace, WorkspaceMember

DEFAULT_CURRENCIES = [
    ('USD', 'US Dollar'),
    ('UAH', 'Ukrainian Hryvnia'),
    ('PLN', 'Polish Zloty'),
    ('EUR', 'Euro'),
]


class WorkspaceService:
    @staticmethod
    @db_transaction.atomic
    def create_workspace(user, name: str, create_demo: bool = False) -> Workspace:
        """
        Creates a workspace with full initial setup:
        - WorkspaceMember (owner role)
        - Default currencies (USD, UAH, PLN, EUR)
        - Default "General" budget account (PLN currency)
        - Demo fixtures (optional)
        - Sets user.current_workspace to the new workspace
        """
        workspace = Workspace.objects.create(name=name, owner=user)
        WorkspaceMember.objects.create(workspace=workspace, user=user, role=Role.OWNER)
        CurrencyService.create_default_currencies(workspace)
        default_currency = workspace.currencies.filter(symbol='PLN').first() or workspace.currencies.first()
        BudgetAccount.objects.create(
            workspace=workspace,
            name='General',
            description='General budget account',
            default_currency=default_currency,
            is_active=True,
            display_order=0,
            created_by=user,
            updated_by=user,
        )

        if create_demo:
            create_demo_fixtures(workspace_id=workspace.id, user_id=user.id)

        user.current_workspace = workspace
        user.save(update_fields=['current_workspace'])

        return workspace

    @staticmethod
    @db_transaction.atomic
    def delete_workspace(user, workspace: Workspace) -> None:
        """
        Deletes workspace and all its data.
        Switches current_workspace for ALL users who had this as their active workspace.
        Raises WorkspaceCannotBeDeletedError if any member has no other workspace.
        """
        from budget_accounts.models import BudgetAccount
        from currency_exchanges.models import CurrencyExchange
        from planned_transactions.models import PlannedTransaction
        from transactions.models import Transaction
        from users.models import User as UserModel

        workspace = Workspace.objects.select_for_update().get(id=workspace.id)
        workspace_id = workspace.id

        members_in_ws = WorkspaceMember.objects.filter(workspace_id=workspace_id).values_list('user_id', flat=True)
        sole_members = (
            UserModel.objects.filter(id__in=members_in_ws)
            .annotate(ws_count=Count('workspace_memberships'))
            .filter(ws_count=1)
        )
        if sole_members.exists():
            raise WorkspaceCannotBeDeletedError()

        affected_users = list(UserModel.objects.filter(current_workspace_id=workspace_id).exclude(id=user.id))

        affected_user_ids = [u.id for u in affected_users] + [user.id]

        next_ws_per_user = (
            WorkspaceMember.objects.filter(user_id__in=affected_user_ids)
            .exclude(workspace_id=workspace_id)
            .values('user_id')
            .annotate(next_ws_id=Min('workspace_id'))
        )
        next_ws_map = {row['user_id']: row['next_ws_id'] for row in next_ws_per_user}

        Transaction.objects.filter(budget_period__budget_account__workspace_id=workspace_id).delete()
        PlannedTransaction.objects.filter(budget_period__budget_account__workspace_id=workspace_id).delete()
        CurrencyExchange.objects.filter(budget_period__budget_account__workspace_id=workspace_id).delete()

        BudgetAccount.objects.filter(workspace_id=workspace_id).delete()

        workspace.delete()

        user.current_workspace_id = next_ws_map.get(user.id)
        user.save(update_fields=['current_workspace'])

        for affected_user in affected_users:
            affected_user.current_workspace_id = next_ws_map.get(affected_user.id)

        UserModel.objects.bulk_update(affected_users, ['current_workspace'])


class CurrencyService:
    @staticmethod
    def list_currencies(workspace_id: int) -> list[Currency]:
        """List all currencies for a workspace."""
        return list(Currency.objects.filter(workspace_id=workspace_id))

    @staticmethod
    def get_currency(currency_id: int, workspace: Workspace) -> Currency | None:
        """Get a currency by ID within a workspace."""
        return Currency.objects.filter(id=currency_id, workspace=workspace).first()

    @staticmethod
    @db_transaction.atomic
    def create_currency(workspace: Workspace, data) -> Currency:
        """Create a new currency for a workspace."""
        if Currency.objects.filter(workspace=workspace, symbol=data.symbol).exists():
            raise CurrencyDuplicateSymbolError(data.symbol)

        return Currency.objects.create(
            workspace=workspace,
            name=data.name,
            symbol=data.symbol,
        )

    @staticmethod
    @db_transaction.atomic
    def delete_currency(currency_id: int, workspace: Workspace) -> None:
        """Delete a currency from a workspace."""
        currency = CurrencyService.get_currency(currency_id, workspace)
        if not currency:
            raise CurrencyNotFoundError()
        currency.delete()

    @staticmethod
    @db_transaction.atomic
    def create_default_currencies(workspace: Workspace) -> list[Currency]:
        """Create the four default currencies for a new workspace."""
        return [
            Currency.objects.create(workspace=workspace, symbol=symbol, name=name)
            for symbol, name in DEFAULT_CURRENCIES
        ]
