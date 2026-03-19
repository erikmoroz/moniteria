"""Domain exceptions for the workspaces app."""

from common.exceptions import NotFoundError, ValidationError


class CurrencyNotFoundError(NotFoundError):
    default_message = 'Currency not found'
    default_code = 'not_found'


class CurrencyDuplicateSymbolError(ValidationError):
    def __init__(self, symbol: str):
        super().__init__(f'Currency with symbol {symbol} already exists in this workspace', code='duplicate_symbol')


class WorkspaceCannotBeDeletedError(ValidationError):
    default_message = (
        'Cannot delete this workspace: one or more members have no other workspace. '
        'Remove those members first or ensure they belong to another workspace.'
    )

    def __init__(self):
        super().__init__(code='workspace_cannot_be_deleted')
