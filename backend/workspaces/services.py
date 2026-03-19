"""Business logic for the workspaces app."""

from django.db import transaction as db_transaction

from budget_accounts.models import BudgetAccount
from workspaces.demo_fixtures import create_demo_fixtures
from workspaces.exceptions import (
    CurrencyDuplicateSymbolError,
    CurrencyNotFoundError,
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
        Users with no other workspace will have current_workspace set to None.
        """
        from budget_accounts.models import BudgetAccount
        from currency_exchanges.models import CurrencyExchange
        from planned_transactions.models import PlannedTransaction
        from transactions.models import Transaction
        from users.models import User as UserModel

        workspace = Workspace.objects.select_for_update().get(id=workspace.id)
        workspace_id = workspace.id

        affected_users = list(UserModel.objects.filter(current_workspace_id=workspace_id).exclude(id=user.id))

        affected_user_ids = [u.id for u in affected_users] + [user.id]

        list(UserModel.objects.filter(id__in=affected_user_ids).select_for_update())

        memberships = (
            WorkspaceMember.objects.filter(user_id__in=affected_user_ids)
            .exclude(workspace_id=workspace_id)
            .order_by('-updated_at')
            .values_list('user_id', 'workspace_id')
        )
        next_ws_map: dict[int, int] = {}
        for uid, wid in memberships:
            if uid not in next_ws_map:
                next_ws_map[uid] = wid

        # -----------------------------------------------------------------------
        # Deletion order matters due to FK constraints:
        #
        # 1. Transaction, PlannedTransaction, CurrencyExchange
        #    - These have currency FK with on_delete=PROTECT, so they must be
        #      deleted before their Currency (which CASCADE-deletes with Workspace).
        #    - They also have budget_period FK (SET_NULL) — safe, but explicit
        #      deletion avoids orphaned rows.
        #
        # 2. CurrencyExchange with budget_period=NULL
        #    - Orphaned exchanges whose period was already deleted; matched by
        #      from_currency__workspace_id instead.
        #
        # 3. BudgetAccount
        #    - CASCADE deletes: BudgetPeriod → Category, Budget, PeriodBalance
        #    - BudgetAccount.default_currency has PROTECT, but currencies still
        #      exist at this point (deleted when Workspace.delete() cascades).
        #
        # 4. Workspace.delete()
        #    - CASCADE deletes: Currency, WorkspaceMember
        # -----------------------------------------------------------------------
        Transaction.objects.filter(budget_period__budget_account__workspace_id=workspace_id).delete()
        PlannedTransaction.objects.filter(budget_period__budget_account__workspace_id=workspace_id).delete()
        CurrencyExchange.objects.filter(budget_period__budget_account__workspace_id=workspace_id).delete()
        CurrencyExchange.objects.filter(
            budget_period__isnull=True,
            from_currency__workspace_id=workspace_id,
        ).delete()

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
    def get_currency(currency_id: int, workspace_id: int) -> Currency | None:
        """Get a currency by ID within a workspace."""
        return Currency.objects.filter(id=currency_id, workspace_id=workspace_id).first()

    @staticmethod
    @db_transaction.atomic
    def create_currency(workspace_id: int, data) -> Currency:
        """Create a new currency for a workspace."""
        if Currency.objects.filter(workspace_id=workspace_id, symbol=data.symbol).exists():
            raise CurrencyDuplicateSymbolError(data.symbol)

        return Currency.objects.create(
            workspace_id=workspace_id,
            name=data.name,
            symbol=data.symbol,
        )

    @staticmethod
    @db_transaction.atomic
    def delete_currency(currency_id: int, workspace_id: int) -> None:
        """Delete a currency from a workspace."""
        currency = CurrencyService.get_currency(currency_id, workspace_id)
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
