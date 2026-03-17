"""Custom exceptions for planned_transactions app."""

from common.exceptions import NotFoundError, ValidationError


class PlannedTransactionNotFoundError(NotFoundError):
    default_message = 'Planned transaction not found'

    def __init__(self, message: str | None = None):
        super().__init__(message, code='not_found')


class PlannedTransactionPeriodNotFoundError(NotFoundError):
    default_message = 'Budget period not found'

    def __init__(self, message: str | None = None):
        super().__init__(message, code='period_not_found')


class PlannedTransactionNoActivePeriodError(NotFoundError):
    default_message = 'No active budget period for the planned transaction date'

    def __init__(self, message: str | None = None):
        super().__init__(message, code='no_active_period')


class PlannedTransactionCategoryNotFoundError(ValidationError):
    default_message = 'Category not found or does not belong to the specified budget period'

    def __init__(self, message: str | None = None):
        super().__init__(message, code='category_not_found')


class PlannedTransactionCurrencyNotFoundError(ValidationError):
    def __init__(self, currency: str):
        super().__init__(f'Currency {currency} not found in workspace', code='currency_not_found')


class PlannedTransactionAlreadyExecutedError(ValidationError):
    default_message = 'Already executed'

    def __init__(self, message: str | None = None):
        super().__init__(message, code='already_executed')


class PlannedTransactionImportError(ValidationError):
    def __init__(self, message: str):
        super().__init__(message, code='import_error')
