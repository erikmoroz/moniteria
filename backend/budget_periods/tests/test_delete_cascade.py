from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget_accounts.models import BudgetAccount
from budget_periods.models import BudgetPeriod
from budget_periods.services import BudgetPeriodService
from common.services.base import delete_workspace_financial_records
from currency_exchanges.models import CurrencyExchange
from planned_transactions.models import PlannedTransaction
from transactions.models import Transaction
from workspaces.models import Currency, Workspace

User = get_user_model()


class TestDeleteCascade(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='testuser@example.com', password='password')
        self.workspace = Workspace.objects.create(name='Test Workspace', owner=self.user)
        self.currency = Currency.objects.create(workspace=self.workspace, symbol='USD', name='US Dollar')
        self.budget_account = BudgetAccount.objects.create(
            workspace=self.workspace, name='Test Account', default_currency=self.currency, created_by=self.user
        )
        self.period = BudgetPeriod.objects.create(
            budget_account=self.budget_account,
            name='Test Period',
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            created_by=self.user,
        )

    def test_budget_period_delete_cascades_financial_records(self):
        """Test that deleting a period deletes its financial records."""
        # Create records
        Transaction.objects.create(
            budget_period=self.period, currency=self.currency, amount=100, date=date(2025, 1, 15), created_by=self.user
        )
        PlannedTransaction.objects.create(
            budget_period=self.period,
            currency=self.currency,
            amount=200,
            planned_date=date(2025, 1, 20),
            created_by=self.user,
        )
        CurrencyExchange.objects.create(
            budget_period=self.period,
            from_currency=self.currency,
            to_currency=self.currency,
            from_amount=10,
            to_amount=10,
            exchange_rate=1,
            date=date(2025, 1, 10),
            created_by=self.user,
        )

        # Ensure they exist
        self.assertEqual(Transaction.objects.filter(budget_period=self.period).count(), 1)
        self.assertEqual(PlannedTransaction.objects.filter(budget_period=self.period).count(), 1)
        self.assertEqual(CurrencyExchange.objects.filter(budget_period=self.period).count(), 1)

        # Delete period via service
        BudgetPeriodService.delete(self.workspace.id, self.period.id)

        # Verify all are deleted
        self.assertFalse(BudgetPeriod.objects.filter(id=self.period.id).exists())
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(PlannedTransaction.objects.count(), 0)
        self.assertEqual(CurrencyExchange.objects.count(), 0)

    def test_delete_workspace_financial_records_catches_orphans(self):
        """Test that orphaned records are deleted by delete_workspace_financial_records."""
        # Create records with budget_period=None manually (simulating pre-fix state)
        # Note: We need to use .update() or bypass the service to create orphans if the model allowed it.
        # The problem was they were orphaned when period was deleted due to SET_NULL.

        t = Transaction.objects.create(
            budget_period=self.period, currency=self.currency, amount=100, date=date(2025, 1, 15), created_by=self.user
        )
        pt = PlannedTransaction.objects.create(
            budget_period=self.period,
            currency=self.currency,
            amount=200,
            planned_date=date(2025, 1, 20),
            created_by=self.user,
        )

        # Manually orphan them by deleting the period directly (not via service)
        # Assuming the model has on_delete=SET_NULL
        self.period.delete()

        t.refresh_from_db()
        pt.refresh_from_db()
        self.assertIsNone(t.budget_period)
        self.assertIsNone(pt.budget_period)

        # Call cleanup service
        delete_workspace_financial_records(self.workspace.id)

        # Verify they are deleted
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(PlannedTransaction.objects.count(), 0)
