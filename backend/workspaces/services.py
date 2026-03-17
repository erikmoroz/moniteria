"""Business logic for the workspaces app."""

from django.db import transaction as db_transaction

from budget_accounts.models import BudgetAccount
from workspaces.exceptions import CurrencyDuplicateSymbolError, CurrencyNotFoundError
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
    def create_workspace(user, name: str, create_demo: bool = True) -> Workspace:
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
        )

        if create_demo:
            from core.demo_fixtures import create_demo_fixtures

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
        The requesting user is switched to their next available workspace, or None.
        """
        from budget_accounts.models import BudgetAccount
        from currency_exchanges.models import CurrencyExchange
        from planned_transactions.models import PlannedTransaction
        from transactions.models import Transaction
        from users.models import User as UserModel

        workspace_id = workspace.id

        affected_users = list(UserModel.objects.filter(current_workspace_id=workspace_id).exclude(id=user.id))

        next_workspace = Workspace.objects.filter(members__user=user).exclude(id=workspace_id).first()

        Transaction.objects.filter(currency__workspace_id=workspace_id).delete()
        PlannedTransaction.objects.filter(currency__workspace_id=workspace_id).delete()
        CurrencyExchange.objects.filter(from_currency__workspace_id=workspace_id).delete()

        BudgetAccount.objects.filter(workspace_id=workspace_id).delete()

        workspace.delete()

        user.current_workspace = next_workspace
        user.save(update_fields=['current_workspace'])

        for affected_user in affected_users:
            next_ws = Workspace.objects.filter(members__user=affected_user).first()
            affected_user.current_workspace = next_ws
            affected_user.save(update_fields=['current_workspace'])


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
