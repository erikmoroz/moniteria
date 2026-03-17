"""Domain exceptions for the workspaces app."""

from common.exceptions import NotFoundError, ServiceError, ValidationError


class CurrencyNotFoundError(NotFoundError):
    default_message = 'Currency not found'

    def __init__(self, message: str | None = None):
        super().__init__(message, code='not_found')


class CurrencyDuplicateSymbolError(ValidationError):
    def __init__(self, symbol: str):
        super().__init__(f'Currency with symbol {symbol} already exists in this workspace', code='duplicate_symbol')


class WorkspaceCannotBeDeletedError(ServiceError):
    http_status = 400
    message = (
        'Cannot delete this workspace: one or more members have no other workspace. '
        'Remove those members first or ensure they belong to another workspace.'
    )

    def __init__(self):
        super().__init__(self.message, code='workspace_cannot_be_deleted')
