"""Custom exceptions for budgets app."""

from common.exceptions import NotFoundError, ValidationError


class BudgetNotFoundError(NotFoundError):
    default_message = 'Budget not found'

    def __init__(self, message: str | None = None):
        super().__init__(message, code='not_found')


from budget_periods.exceptions import BudgetPeriodNotFoundError  # noqa: E402, F401


class BudgetCategoryNotFoundError(ValidationError):
    default_message = 'Category not found or does not belong to the specified budget period'

    def __init__(self, message: str | None = None):
        super().__init__(message, code='category_not_found')


class BudgetCurrencyNotFoundError(ValidationError):
    def __init__(self, currency: str):
        super().__init__(f'Currency {currency} not found in workspace', code='currency_not_found')
