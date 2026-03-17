"""Shared permission utilities for API endpoints."""

from ninja.errors import HttpError

from workspaces.models import WorkspaceMember


def require_role(user, workspace_id: int, allowed_roles: list[str]) -> str:
    """Raise 403 if user is not a member or their role is not in allowed_roles. Returns the role."""
    try:
        member = WorkspaceMember.objects.get(workspace_id=workspace_id, user=user)
        role = member.role
    except WorkspaceMember.DoesNotExist:
        raise HttpError(403, 'Not a member of this workspace')
    if role not in allowed_roles:
        raise HttpError(403, f'Insufficient permissions. Required: {", ".join(allowed_roles)}. Your role: {role}')
    return role
