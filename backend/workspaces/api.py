"""Django-Ninja API endpoints for workspaces app."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from common.auth import JWTAuth, WorkspaceJWTAuth
from common.permissions import require_role
from core.schemas import MessageOut
from workspaces.models import ADMIN_ROLES, Role, Workspace, WorkspaceMember
from workspaces.schemas import (
    CurrencyCreate,
    CurrencyOut,
    MemberPasswordReset,
    WorkspaceCreate,
    WorkspaceMemberAdd,
    WorkspaceMemberOut,
    WorkspaceMemberRoleUpdate,
    WorkspaceOut,
    WorkspaceUpdate,
)
from workspaces.services import CurrencyService, WorkspaceService

router = Router(tags=['Workspaces'])
User = get_user_model()


# =============================================================================
# Currency Endpoints
# =============================================================================


@router.get('/currencies', response=list[CurrencyOut], auth=WorkspaceJWTAuth())
def list_currencies(request: HttpRequest):
    """List all currencies for the current workspace."""
    return CurrencyService.list_currencies(request.auth.current_workspace_id)


@router.post('/currencies', response={201: CurrencyOut}, auth=WorkspaceJWTAuth())
def create_currency(request: HttpRequest, data: CurrencyCreate):
    """Create a new currency for the current workspace."""
    workspace_id = request.auth.current_workspace_id
    require_role(request.auth, workspace_id, ADMIN_ROLES)
    currency = CurrencyService.create_currency(workspace_id, data)
    return 201, currency


@router.delete('/currencies/{currency_id}', response={204: None}, auth=WorkspaceJWTAuth())
def delete_currency(request: HttpRequest, currency_id: int):
    """Delete a currency from the current workspace."""
    workspace_id = request.auth.current_workspace_id
    require_role(request.auth, workspace_id, ADMIN_ROLES)
    CurrencyService.delete_currency(currency_id, workspace_id)
    return 204, None


# =============================================================================
# Helper Functions
# =============================================================================


def validate_workspace_access(workspace_id: int, user) -> Workspace:
    """Validate that the workspace exists and the user is a member of it."""
    workspace = Workspace.objects.filter(id=workspace_id).first()
    if not workspace:
        raise HttpError(404, 'Workspace not found')

    member = WorkspaceMember.objects.filter(
        workspace_id=workspace_id,
        user=user,
    ).first()
    if not member:
        raise HttpError(404, 'Workspace not found')

    return workspace


# =============================================================================
# Workspace Endpoints
# =============================================================================


@router.get('', response=list[WorkspaceOut], auth=JWTAuth())
def list_workspaces(request: HttpRequest):
    """List all workspaces the current user has access to."""
    user = request.auth

    memberships = WorkspaceMember.objects.filter(user_id=user.id).select_related('workspace')

    result = []
    for m in memberships:
        ws = m.workspace
        ws.user_role = m.role
        result.append(ws)

    return result


@router.post('/', response={201: WorkspaceOut}, auth=JWTAuth())
def create_workspace_endpoint(request: HttpRequest, data: WorkspaceCreate):
    """Create a new workspace. User becomes owner and is auto-switched to it."""
    workspace = WorkspaceService.create_workspace(user=request.auth, name=data.name, create_demo=False)
    workspace.user_role = Role.OWNER
    return 201, workspace


# IMPORTANT: /current routes must come BEFORE /{workspace_id} routes
@router.get('/current', response=WorkspaceOut, auth=WorkspaceJWTAuth())
def get_current_workspace_info(request: HttpRequest):
    """Get current workspace details."""
    user = request.auth
    workspace_id = user.current_workspace_id
    try:
        member = WorkspaceMember.objects.select_related('workspace').get(workspace_id=workspace_id, user=user)
    except WorkspaceMember.DoesNotExist:
        raise HttpError(404, 'Workspace not found')
    workspace = member.workspace
    workspace.user_role = member.role
    return workspace


@router.put('/current', response=WorkspaceOut, auth=WorkspaceJWTAuth())
def update_current_workspace(request: HttpRequest, data: WorkspaceUpdate):
    """Update current workspace (requires owner or admin role)."""
    workspace_id = request.auth.current_workspace_id
    user_role = require_role(request.auth, workspace_id, ADMIN_ROLES)
    workspace = Workspace.objects.get(id=workspace_id)

    if data.name is not None:
        workspace.name = data.name
        workspace.save()

    workspace.user_role = user_role
    return workspace


@router.delete('/{workspace_id}', response={204: None}, auth=JWTAuth())
def delete_workspace_endpoint(request: HttpRequest, workspace_id: int):
    """Delete a workspace. Only the owner can delete it."""
    workspace = validate_workspace_access(workspace_id, request.auth)
    require_role(request.auth, workspace_id, [Role.OWNER])
    WorkspaceService.delete_workspace(user=request.auth, workspace=workspace)
    return 204, None


@router.post('/{workspace_id}/switch', response=MessageOut, auth=JWTAuth())
def switch_workspace(request: HttpRequest, workspace_id: int):
    """Switch to a different workspace."""
    user = request.auth

    # Verify user has access to this workspace
    member = WorkspaceMember.objects.filter(
        workspace_id=workspace_id,
        user_id=user.id,
    ).first()

    if not member:
        raise HttpError(404, 'Workspace not found')

    # Update user's current workspace
    user.current_workspace_id = workspace_id
    user.save(update_fields=['current_workspace'])

    return {'message': 'Workspace switched successfully', 'workspace_id': workspace_id}


# =============================================================================
# Workspace Members Endpoints
# =============================================================================

# IMPORTANT: Specific routes must come BEFORE parameterized routes to avoid
# path matching issues (e.g., "leave" or "add" being matched as {member_user_id})


@router.get('/{workspace_id}/members', response=list[WorkspaceMemberOut], auth=JWTAuth())
def list_workspace_members(request: HttpRequest, workspace_id: int):
    """
    List all members in the workspace.
    Any workspace member can view the member list.
    """
    user = request.auth

    # Validate user has access to this workspace
    validate_workspace_access(workspace_id, user)

    members_with_users = (
        WorkspaceMember.objects.filter(workspace_id=workspace_id)
        .select_related('user')
        .order_by('-role', 'user__email')
    )

    return [
        {
            'id': member.id,
            'workspace_id': member.workspace_id,
            'user_id': member.user_id,
            'email': member.user.email,
            'full_name': member.user.full_name,
            'role': member.role,
            'is_active': member.user.is_active,
            'created_at': member.created_at,
        }
        for member in members_with_users
    ]


@router.post('/{workspace_id}/members/add', response={201: dict, 400: dict}, auth=JWTAuth())
def add_member_to_workspace(request: HttpRequest, workspace_id: int, data: WorkspaceMemberAdd):
    """
    Add a new member to the workspace.

    Behavior:
    - If user exists: Add them to workspace (password ignored)
    - If user doesn't exist: Create user with provided password, add to workspace
    """
    user = request.auth

    # Validate workspace access
    validate_workspace_access(workspace_id, user)

    # Check current user has admin/owner role
    require_role(user, workspace_id, ADMIN_ROLES)

    # Check workspace member limit (15 members maximum)
    current_member_count = WorkspaceMember.objects.filter(workspace_id=workspace_id).count()

    if current_member_count >= settings.WORKSPACE_MAX_MEMBERS:
        return 400, {
            'detail': f'Workspace member limit reached. Maximum {settings.WORKSPACE_MAX_MEMBERS} members allowed per workspace.'
        }

    # Check if user already exists
    existing_user = User.objects.filter(email=data.email).first()

    if existing_user:
        # Check if already a member of this workspace
        existing_member = WorkspaceMember.objects.filter(
            workspace_id=workspace_id,
            user_id=existing_user.id,
        ).first()

        if existing_member:
            return 400, {'detail': 'User is already a member of this workspace'}

        # Add existing user to workspace. Do not change their active workspace; they choose when to switch.
        new_member = WorkspaceMember.objects.create(
            workspace_id=workspace_id,
            user_id=existing_user.id,
            role=data.role,
        )

        return 201, {
            'message': f'Existing user {data.email} added to workspace',
            'user_id': existing_user.id,
            'member_id': new_member.id,
            'is_new_user': False,
        }
    else:
        # Create new user with provided password
        if not data.password:
            return 400, {'detail': 'Password is required when adding a new user.'}
        new_user = User.objects.create_user(
            email=data.email,
            password=data.password,
            full_name=data.full_name,
            # New user has no workspace yet — set it to this workspace so they can log in immediately.
            current_workspace_id=workspace_id,
            is_active=True,
        )

        # Add to workspace
        new_member = WorkspaceMember.objects.create(
            workspace_id=workspace_id,
            user_id=new_user.id,
            role=data.role,
        )

        return 201, {
            'message': f'User {data.email} created and added to workspace',
            'user_id': new_user.id,
            'member_id': new_member.id,
            'is_new_user': True,
        }


@router.post('/{workspace_id}/members/leave', response=MessageOut, auth=JWTAuth())
def leave_workspace(request: HttpRequest, workspace_id: int):
    """
    Leave the workspace (remove yourself).

    Business rules:
    - Owner cannot leave (must transfer ownership first)
    """
    user = request.auth

    # Validate workspace access
    validate_workspace_access(workspace_id, user)

    member = WorkspaceMember.objects.filter(
        workspace_id=workspace_id,
        user_id=user.id,
    ).first()

    if not member:
        raise HttpError(404, 'You are not a member of this workspace')

    # Owner cannot leave
    if member.role == Role.OWNER:
        raise HttpError(400, 'Workspace owner cannot leave. Transfer ownership first or delete the workspace.')

    with db_transaction.atomic():
        member.delete()

        if user.current_workspace_id == workspace_id:
            next_workspace = Workspace.objects.filter(members__user=user).exclude(id=workspace_id).first()
            user.current_workspace = next_workspace
            user.save(update_fields=['current_workspace'])

    return {'message': 'Successfully left workspace'}


@router.put('/{workspace_id}/members/{member_user_id}/role', response=dict, auth=JWTAuth())
def update_member_role(
    request: HttpRequest,
    workspace_id: int,
    member_user_id: int,
    data: WorkspaceMemberRoleUpdate,
):
    """
    Update a member's role in the workspace.

    Business rules:
    - Cannot change owner role (only one owner per workspace)
    - Admin cannot change other admins or owner
    - Cannot change your own role
    """
    user = request.auth

    # Validate workspace access
    validate_workspace_access(workspace_id, user)

    # Check current user has admin/owner role
    current_role = require_role(user, workspace_id, ADMIN_ROLES)

    # Get the member record
    member = WorkspaceMember.objects.filter(
        workspace_id=workspace_id,
        user_id=member_user_id,
    ).first()

    if not member:
        raise HttpError(404, 'Member not found in this workspace')

    # Cannot change your own role
    if member_user_id == user.id:
        raise HttpError(400, 'Cannot change your own role')

    # Cannot change owner role
    if member.role == Role.OWNER:
        raise HttpError(400, "Cannot change the owner's role")

    # Admin cannot change other admin's role
    if current_role == Role.ADMIN and member.role == Role.ADMIN:
        raise HttpError(403, "Admin cannot change another admin's role. Owner required.")

    # Update the role
    old_role = member.role
    member.role = data.role
    member.save()

    return {
        'message': 'Role updated successfully',
        'user_id': member_user_id,
        'old_role': old_role,
        'new_role': data.role,
    }


@router.delete('/{workspace_id}/members/{member_user_id}', response={204: None}, auth=JWTAuth())
def remove_member_from_workspace(request: HttpRequest, workspace_id: int, member_user_id: int):
    """
    Remove a member from the workspace.

    Business rules:
    - Cannot remove owner
    - Admin cannot remove other admins
    - Cannot remove yourself (use leave endpoint instead)
    """
    user = request.auth

    # Validate workspace access
    validate_workspace_access(workspace_id, user)

    # Check current user has admin/owner role
    current_role = require_role(user, workspace_id, ADMIN_ROLES)

    # Get the member record
    member = WorkspaceMember.objects.filter(
        workspace_id=workspace_id,
        user_id=member_user_id,
    ).first()

    if not member:
        raise HttpError(404, 'Member not found in this workspace')

    # Cannot remove yourself
    if member_user_id == user.id:
        raise HttpError(400, 'Cannot remove yourself. Use the leave endpoint instead.')

    # Cannot remove owner
    if member.role == Role.OWNER:
        raise HttpError(400, 'Cannot remove the workspace owner')

    # Admin cannot remove other admin
    if current_role == Role.ADMIN and member.role == Role.ADMIN:
        raise HttpError(403, 'Admin cannot remove another admin. Owner required.')

    with db_transaction.atomic():
        member.delete()

        removed_user = User.objects.filter(id=member_user_id).first()
        if removed_user and removed_user.current_workspace_id == workspace_id:
            next_workspace = Workspace.objects.filter(members__user=removed_user).first()
            removed_user.current_workspace = next_workspace
            removed_user.save(update_fields=['current_workspace'])

    return 204, None


@router.put('/{workspace_id}/members/{user_id}/reset-password', response=MessageOut, auth=JWTAuth())
def reset_member_password(
    request: HttpRequest,
    workspace_id: int,
    user_id: int,
    data: MemberPasswordReset,
):
    """
    Reset a workspace member's password (admin action).

    Security rules:
    - Owner can reset password for: admin, member, viewer
    - Admin can reset password for: member, viewer only (NOT other admins)
    - Cannot reset own password (use change password feature instead)
    - Cannot reset owner's password
    """
    user = request.auth

    # Validate workspace access
    validate_workspace_access(workspace_id, user)

    # Check current user has admin/owner role
    current_role = require_role(user, workspace_id, ADMIN_ROLES)

    # Get the target member's record
    target_member = WorkspaceMember.objects.filter(
        workspace_id=workspace_id,
        user_id=user_id,
    ).first()

    if not target_member:
        raise HttpError(404, 'Member not found in this workspace')

    # Cannot reset own password
    if user_id == user.id:
        raise HttpError(400, 'Cannot reset your own password. Use the change password feature instead.')

    # Cannot reset owner's password
    if target_member.role == Role.OWNER:
        raise HttpError(400, "Cannot reset the owner's password")

    # Admin cannot reset another admin's password
    if current_role == Role.ADMIN and target_member.role == Role.ADMIN:
        raise HttpError(403, "Admin cannot reset another admin's password. Owner required.")

    # Get the target user and update password
    target_user = User.objects.filter(id=user_id).first()
    if not target_user:
        raise HttpError(404, 'User not found')

    target_user.set_password(data.new_password)
    target_user.save()

    return {
        'message': 'Password reset successfully',
        'user_id': user_id,
        'email': target_user.email,
    }
