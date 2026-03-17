"""Tests for WorkspaceService and CurrencyService."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget_accounts.models import BudgetAccount
from common.tests.factories import UserFactory
from workspaces.factories import WorkspaceFactory
from workspaces.exceptions import CurrencyDuplicateSymbolError, CurrencyNotFoundError
from workspaces.models import Currency, Workspace, WorkspaceMember
from workspaces.services import CurrencyService, WorkspaceService

User = get_user_model()


class TestWorkspaceServiceCreateWorkspace(TestCase):
    """Tests for WorkspaceService.create_workspace()."""

    def test_creates_workspace_with_owner_membership(self):
        """Test that create_workspace creates workspace with owner membership."""
        user = UserFactory()
        workspace = WorkspaceService.create_workspace(user=user, name='Test Workspace', create_demo=False)

        self.assertIsInstance(workspace, Workspace)
        self.assertEqual(workspace.name, 'Test Workspace')
        self.assertEqual(workspace.owner, user)

        membership = WorkspaceMember.objects.filter(workspace=workspace, user=user).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, 'owner')

    def test_creates_default_currencies(self):
        """Test that create_workspace creates 4 default currencies."""
        user = UserFactory()
        workspace = WorkspaceService.create_workspace(user=user, name='Test Workspace', create_demo=False)

        currencies = list(Currency.objects.filter(workspace=workspace))
        self.assertEqual(len(currencies), 4)

        symbols = {c.symbol for c in currencies}
        self.assertEqual(symbols, {'USD', 'UAH', 'PLN', 'EUR'})

    def test_creates_general_budget_account_with_all_fields(self):
        """Test that create_workspace creates General BudgetAccount with all required fields."""
        user = UserFactory()
        workspace = WorkspaceService.create_workspace(user=user, name='Test Workspace', create_demo=False)

        account = BudgetAccount.objects.filter(workspace=workspace, name='General').first()
        self.assertIsNotNone(account)
        self.assertEqual(account.description, 'General budget account')
        self.assertEqual(account.display_order, 0)
        self.assertEqual(account.created_by, user)
        self.assertTrue(account.is_active)

        pln = Currency.objects.get(workspace=workspace, symbol='PLN')
        self.assertEqual(account.default_currency, pln)

    def test_sets_user_current_workspace(self):
        """Test that create_workspace sets user.current_workspace to the new workspace."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            full_name='Test User',
        )
        self.assertIsNone(user.current_workspace)

        workspace = WorkspaceService.create_workspace(user=user, name='Test Workspace', create_demo=False)

        user.refresh_from_db()
        self.assertEqual(user.current_workspace, workspace)

    def test_with_create_demo_false_skips_demo_fixtures(self):
        """Test that create_demo=False skips demo fixtures but still creates currencies and account."""
        user = UserFactory()
        workspace = WorkspaceService.create_workspace(user=user, name='Test Workspace', create_demo=False)

        currencies_count = Currency.objects.filter(workspace=workspace).count()
        self.assertEqual(currencies_count, 4)

        account_count = BudgetAccount.objects.filter(workspace=workspace).count()
        self.assertEqual(account_count, 1)


class TestWorkspaceServiceDeleteWorkspace(TestCase):
    """Tests for WorkspaceService.delete_workspace()."""

    def test_deletes_workspace_and_all_data(self):
        """Test that delete_workspace cascades all data."""
        user = UserFactory()
        workspace = WorkspaceService.create_workspace(user=user, name='Test Workspace', create_demo=False)

        workspace_id = workspace.id
        WorkspaceService.delete_workspace(user=user, workspace=workspace)

        self.assertFalse(Workspace.objects.filter(id=workspace_id).exists())
        self.assertFalse(WorkspaceMember.objects.filter(workspace_id=workspace_id).exists())
        self.assertFalse(Currency.objects.filter(workspace_id=workspace_id).exists())
        self.assertFalse(BudgetAccount.objects.filter(workspace_id=workspace_id).exists())

    def test_switches_user_to_next_workspace(self):
        """Test that delete_workspace switches requesting user to next workspace."""
        user = UserFactory()
        ws1 = WorkspaceService.create_workspace(user=user, name='Workspace 1', create_demo=False)
        ws2 = WorkspaceService.create_workspace(user=user, name='Workspace 2', create_demo=False)

        user.refresh_from_db()
        self.assertEqual(user.current_workspace, ws2)

        WorkspaceService.delete_workspace(user=user, workspace=ws2)

        user.refresh_from_db()
        self.assertEqual(user.current_workspace, ws1)

    def test_switches_user_to_none_if_no_other_workspace(self):
        """Test that delete_workspace sets current_workspace to None if no other workspace."""
        user = UserFactory()
        workspace = WorkspaceService.create_workspace(user=user, name='Test Workspace', create_demo=False)

        WorkspaceService.delete_workspace(user=user, workspace=workspace)

        user.refresh_from_db()
        self.assertIsNone(user.current_workspace)

    def test_switches_all_affected_users(self):
        """Test that delete_workspace switches ALL users who had this as current workspace."""
        owner = UserFactory()
        member = UserFactory()

        workspace = WorkspaceService.create_workspace(user=owner, name='Test Workspace', create_demo=False)

        WorkspaceMember.objects.create(workspace=workspace, user=member, role='member')
        member.current_workspace = workspace
        member.save()

        owner.current_workspace = workspace
        owner.save()

        WorkspaceService.delete_workspace(user=owner, workspace=workspace)

        owner.refresh_from_db()
        member.refresh_from_db()
        self.assertIsNone(owner.current_workspace)
        self.assertIsNone(member.current_workspace)


class TestCurrencyService(TestCase):
    """Tests for CurrencyService."""

    def test_list_currencies(self):
        """Test listing currencies for a workspace."""
        workspace = WorkspaceFactory()
        currencies = CurrencyService.list_currencies(workspace.id)
        self.assertEqual(len(currencies), 4)

    def test_get_currency(self):
        """Test getting a currency by ID within a workspace."""
        workspace = WorkspaceFactory()
        pln = Currency.objects.get(workspace=workspace, symbol='PLN')

        result = CurrencyService.get_currency(pln.id, workspace)
        self.assertEqual(result, pln)

    def test_get_currency_wrong_workspace(self):
        """Test that get_currency returns None for wrong workspace."""
        workspace1 = WorkspaceFactory()
        workspace2 = WorkspaceFactory()

        pln = Currency.objects.get(workspace=workspace1, symbol='PLN')
        result = CurrencyService.get_currency(pln.id, workspace2)
        self.assertIsNone(result)

    def test_create_currency(self):
        """Test creating a new currency."""
        workspace = WorkspaceFactory()

        class Data:
            symbol = 'GBP'
            name = 'British Pound'

        currency = CurrencyService.create_currency(workspace, Data())
        self.assertEqual(currency.symbol, 'GBP')
        self.assertEqual(currency.name, 'British Pound')
        self.assertEqual(currency.workspace, workspace)

    def test_create_duplicate_currency_fails(self):
        """Test that creating duplicate currency symbol raises CurrencyDuplicateSymbolError."""
        workspace = WorkspaceFactory()

        class Data:
            symbol = 'PLN'
            name = 'Polish Zloty'

        with self.assertRaises(CurrencyDuplicateSymbolError):
            CurrencyService.create_currency(workspace, Data())

    def test_delete_currency(self):
        """Test deleting a currency."""
        workspace = WorkspaceFactory()
        usd = Currency.objects.get(workspace=workspace, symbol='USD')

        CurrencyService.delete_currency(usd.id, workspace)

        self.assertFalse(Currency.objects.filter(id=usd.id).exists())

    def test_delete_currency_wrong_workspace(self):
        """Test that deleting currency from wrong workspace raises CurrencyNotFoundError."""
        workspace1 = WorkspaceFactory()
        workspace2 = WorkspaceFactory()

        usd = Currency.objects.get(workspace=workspace1, symbol='USD')

        with self.assertRaises(CurrencyNotFoundError):
            CurrencyService.delete_currency(usd.id, workspace2)
