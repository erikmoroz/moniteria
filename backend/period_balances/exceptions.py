"""Custom exceptions for period_balances app."""

from common.exceptions import NotFoundError, ValidationError


class PeriodBalanceNotFoundError(NotFoundError):
    default_message = 'Period balance not found'

    def __init__(self, message: str | None = None):
        super().__init__(message, code='not_found')


class PeriodBalancePeriodNotFoundError(NotFoundError):
    default_message = 'Budget period not found'

    def __init__(self, message: str | None = None):
        super().__init__(message, code='period_not_found')


class PeriodBalanceCurrencyNotFoundError(ValidationError):
    def __init__(self, currency: str):
        super().__init__(f'Currency {currency} not found in workspace', code='currency_not_found')
