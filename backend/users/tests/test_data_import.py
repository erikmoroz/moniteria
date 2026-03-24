"""Tests for GDPR data import."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from common.tests.mixins import AuthMixin
from users.services import UserService

User = get_user_model()


class DataImportTests(AuthMixin, TestCase):
    """Tests for GDPR data import service."""

    def test_import_rejects_incompatible_version(self):
        """Import should reject exports with version 1.x."""
        export_data = {
            'export_version': '1.0',
            'workspaces': [],
        }

        from common.exceptions import ValidationError

        with self.assertRaises(ValidationError) as ctx:
            UserService.import_all_data(self.user, self._make_import_input(export_data))

        self.assertIn('Incompatible export version', str(ctx.exception.message))

    def test_import_accepts_version_2_0(self):
        """Import should accept exports with version 2.0."""
        export_data = {
            'export_version': '2.0',
            'workspaces': [],
        }

        result = UserService.import_all_data(self.user, self._make_import_input(export_data))

        self.assertEqual(result['imported_workspaces'], 0)

    def test_import_creates_workspace(self):
        """Import should create a new workspace."""
        export_data = self._create_sample_export()

        result = UserService.import_all_data(self.user, self._make_import_input(export_data))

        self.assertEqual(result['imported_workspaces'], 1)
        self.assertTrue(User.objects.filter(email=self.user.email).first().current_workspace is not None)

    def test_import_skips_existing_workspace_with_skip_strategy(self):
        """Import with skip strategy should skip existing workspace."""
        export_data = self._create_sample_export()

        result = UserService.import_all_data(
            self.user,
            self._make_import_input(export_data, conflict_strategy='skip'),
        )

        self.assertEqual(result['imported_workspaces'], 1)

        result2 = UserService.import_all_data(
            self.user,
            self._make_import_input(export_data, conflict_strategy='skip'),
        )

        self.assertEqual(result2['imported_workspaces'], 0)
        self.assertIn('Test Import Workspace', result2['skipped']['workspaces'])

    def test_import_renames_workspace_with_rename_strategy(self):
        """Import with rename strategy should rename conflicting workspace."""
        export_data = self._create_sample_export()

        UserService.import_all_data(self.user, self._make_import_input(export_data))

        result = UserService.import_all_data(
            self.user,
            self._make_import_input(export_data, conflict_strategy='rename'),
        )

        self.assertEqual(result['imported_workspaces'], 1)
        self.assertIn('Test Import Workspace', result['renamed'])

    def test_import_filter_workspaces(self):
        """Import should filter workspaces when workspaces parameter is provided."""
        export_data = {
            'export_version': '2.0',
            'workspaces': [
                {'workspace_name': 'Workspace A', 'currencies': [], 'budget_accounts': []},
                {'workspace_name': 'Workspace B', 'currencies': [], 'budget_accounts': []},
            ],
        }

        result = UserService.import_all_data(
            self.user,
            self._make_import_input(export_data, workspaces=['Workspace A']),
        )

        self.assertEqual(result['imported_workspaces'], 1)

    def test_import_creates_budget_account_and_period(self):
        """Import should create budget accounts and periods."""
        export_data = self._create_sample_export_with_account()

        result = UserService.import_all_data(self.user, self._make_import_input(export_data))

        self.assertEqual(result['imported_budget_accounts'], 1)
        self.assertEqual(result['imported_budget_periods'], 1)

    def test_import_creates_transactions(self):
        """Import should create transactions."""
        export_data = self._create_sample_export_with_transactions()

        result = UserService.import_all_data(self.user, self._make_import_input(export_data))

        self.assertEqual(result['imported_transactions'], 2)
        self.assertEqual(result['imported_categories'], 1)

    def test_import_creates_budgets(self):
        """Import should create budgets."""
        export_data = self._create_sample_export_with_budgets()

        result = UserService.import_all_data(self.user, self._make_import_input(export_data))

        self.assertEqual(result['imported_budgets'], 1)

    def test_import_creates_planned_transactions(self):
        """Import should create planned transactions."""
        export_data = self._create_sample_export_with_planned_transactions()

        result = UserService.import_all_data(self.user, self._make_import_input(export_data))

        self.assertEqual(result['imported_planned_transactions'], 1)

    def test_import_creates_currency_exchanges(self):
        """Import should create currency exchanges."""
        export_data = self._create_sample_export_with_currency_exchanges()

        result = UserService.import_all_data(self.user, self._make_import_input(export_data))

        self.assertEqual(result['imported_currency_exchanges'], 1)

    def _make_import_input(self, data, workspaces=None, conflict_strategy='rename'):
        """Create FullImportIn-like object."""
        from core.schemas import FullImportIn

        return FullImportIn(data=data, workspaces=workspaces, conflict_strategy=conflict_strategy)

    def _create_sample_export(self):
        """Create a minimal valid export for testing."""
        return {
            'export_version': '2.0',
            'workspaces': [
                {
                    'workspace_name': 'Test Import Workspace',
                    'currencies': [],
                    'budget_accounts': [],
                }
            ],
        }

    def _create_sample_export_with_account(self):
        """Create an export with budget account and period."""
        return {
            'export_version': '2.0',
            'workspaces': [
                {
                    'workspace_name': 'Test Import Workspace',
                    'currencies': [{'symbol': 'USD', 'name': 'US Dollar'}],
                    'budget_accounts': [
                        {
                            'name': 'Test Account',
                            'description': 'Test description',
                            'default_currency': 'USD',
                            'is_active': True,
                            'periods': [
                                {
                                    'name': 'January 2024',
                                    'start_date': '2024-01-01',
                                    'end_date': '2024-01-31',
                                    'categories': [],
                                    'budgets': [],
                                    'transactions': [],
                                    'planned_transactions': [],
                                    'currency_exchanges': [],
                                    'period_balances': [],
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def _create_sample_export_with_transactions(self):
        """Create an export with transactions."""
        return {
            'export_version': '2.0',
            'workspaces': [
                {
                    'workspace_name': 'Test Import Workspace',
                    'currencies': [{'symbol': 'USD', 'name': 'US Dollar'}],
                    'budget_accounts': [
                        {
                            'name': 'Test Account',
                            'description': 'Test description',
                            'default_currency': 'USD',
                            'is_active': True,
                            'periods': [
                                {
                                    'name': 'January 2024',
                                    'start_date': '2024-01-01',
                                    'end_date': '2024-01-31',
                                    'categories': [{'id': 1, 'name': 'Food'}],
                                    'budgets': [],
                                    'transactions': [
                                        {
                                            'date': '2024-01-15',
                                            'description': 'Groceries',
                                            'amount': '50.00',
                                            'type': 'expense',
                                            'category_name': 'Food',
                                            'currency_symbol': 'USD',
                                        },
                                        {
                                            'date': '2024-01-20',
                                            'description': 'Salary',
                                            'amount': '1000.00',
                                            'type': 'income',
                                            'category_name': None,
                                            'currency_symbol': 'USD',
                                        },
                                    ],
                                    'planned_transactions': [],
                                    'currency_exchanges': [],
                                    'period_balances': [],
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def _create_sample_export_with_budgets(self):
        """Create an export with budgets."""
        return {
            'export_version': '2.0',
            'workspaces': [
                {
                    'workspace_name': 'Test Import Workspace',
                    'currencies': [{'symbol': 'USD', 'name': 'US Dollar'}],
                    'budget_accounts': [
                        {
                            'name': 'Test Account',
                            'description': 'Test description',
                            'default_currency': 'USD',
                            'is_active': True,
                            'periods': [
                                {
                                    'name': 'January 2024',
                                    'start_date': '2024-01-01',
                                    'end_date': '2024-01-31',
                                    'categories': [{'id': 1, 'name': 'Food'}],
                                    'budgets': [
                                        {
                                            'category_name': 'Food',
                                            'amount': '500.00',
                                            'currency_symbol': 'USD',
                                        }
                                    ],
                                    'transactions': [],
                                    'planned_transactions': [],
                                    'currency_exchanges': [],
                                    'period_balances': [],
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def _create_sample_export_with_planned_transactions(self):
        """Create an export with planned transactions."""
        return {
            'export_version': '2.0',
            'workspaces': [
                {
                    'workspace_name': 'Test Import Workspace',
                    'currencies': [{'symbol': 'USD', 'name': 'US Dollar'}],
                    'budget_accounts': [
                        {
                            'name': 'Test Account',
                            'description': 'Test description',
                            'default_currency': 'USD',
                            'is_active': True,
                            'periods': [
                                {
                                    'name': 'January 2024',
                                    'start_date': '2024-01-01',
                                    'end_date': '2024-01-31',
                                    'categories': [],
                                    'budgets': [],
                                    'transactions': [],
                                    'planned_transactions': [
                                        {
                                            'name': 'Rent',
                                            'amount': '1000.00',
                                            'planned_date': '2024-01-01',
                                            'payment_date': None,
                                            'status': 'pending',
                                            'currency_symbol': 'USD',
                                        }
                                    ],
                                    'currency_exchanges': [],
                                    'period_balances': [],
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def _create_sample_export_with_currency_exchanges(self):
        """Create an export with currency exchanges."""
        return {
            'export_version': '2.0',
            'workspaces': [
                {
                    'workspace_name': 'Test Import Workspace',
                    'currencies': [
                        {'symbol': 'USD', 'name': 'US Dollar'},
                        {'symbol': 'EUR', 'name': 'Euro'},
                    ],
                    'budget_accounts': [
                        {
                            'name': 'Test Account',
                            'description': 'Test description',
                            'default_currency': 'USD',
                            'is_active': True,
                            'periods': [
                                {
                                    'name': 'January 2024',
                                    'start_date': '2024-01-01',
                                    'end_date': '2024-01-31',
                                    'categories': [],
                                    'budgets': [],
                                    'transactions': [],
                                    'planned_transactions': [],
                                    'currency_exchanges': [
                                        {
                                            'date': '2024-01-10',
                                            'description': 'USD to EUR',
                                            'from_amount': '100.00',
                                            'to_amount': '92.00',
                                            'exchange_rate': '0.92',
                                            'from_currency_symbol': 'USD',
                                            'to_currency_symbol': 'EUR',
                                        }
                                    ],
                                    'period_balances': [],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
