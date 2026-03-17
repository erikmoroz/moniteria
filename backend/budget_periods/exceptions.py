"""Custom exceptions for budget_periods app."""

from common.exceptions import NotFoundError


class BudgetPeriodNotFoundError(NotFoundError):
    default_message = 'Period not found'

    def __init__(self, message: str | None = None):
        super().__init__(message, code='not_found')
