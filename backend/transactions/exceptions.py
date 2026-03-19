"""Custom exceptions for transactions app."""

from common.exceptions import NotFoundError, ValidationError


class TransactionNotFoundError(NotFoundError):
    default_message = 'Transaction not found'
    default_code = 'not_found'


class TransactionPeriodNotFoundError(ValidationError):
    default_message = 'No active budget period for the transaction date'
    default_code = 'period_not_found'


class TransactionCategoryNotFoundError(ValidationError):
    default_message = 'Category not found or does not belong to the assigned budget period'
    default_code = 'category_not_found'


class TransactionImportError(ValidationError):
    def __init__(self, message: str):
        super().__init__(message, code='import_error')
