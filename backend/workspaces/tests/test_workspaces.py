"""Tests for workspaces and workspace_members API endpoints."""

from django.test import TestCase

from common.tests.factories import UserFactory
from common.tests.mixins import APIClientMixin, AuthMixin
from workspaces.factories import WorkspaceFactory, WorkspaceMemberFactory
from workspaces.models import Workspace, WorkspaceMember

# =============================================================================
# Base Test Class
# =============================================================================


class WorkspaceTestCase(APIClientMixin, AuthMixin, TestCase):
    """Base test case for workspace tests with authenticated user and data."""

    def setUp(self):
        """Set up test data for workspace API tests."""
        APIClientMixin.setUp(self)
        AuthMixin.setUp(self)

        self.admin_user = UserFactory(
            email='admin@example.com',
            current_workspace=self.workspace,
        )
        WorkspaceMemberFactory(
            workspace=self.workspace,
            user=self.admin_user,
            role='admin',
        )

        self.member_user = UserFactory(
            email='member@example.com',
            current_workspace=self.workspace,
        )
        WorkspaceMemberFactory(
            workspace=self.workspace,
            user=self.member_user,
            role='member',
        )

        self.viewer_user = UserFactory(
            email='viewer@example.com',
            current_workspace=self.workspace,
        )
        WorkspaceMemberFactory(
            workspace=self.workspace,
            user=self.viewer_user,
            role='viewer',
        )

        self.other_workspace = WorkspaceFactory(name='Other Workspace')
        WorkspaceMemberFactory(
            workspace=self.other_workspace,
            user=self.user,
            role='admin',
        )


# =============================================================================
# List Workspaces Tests
# =============================================================================


class TestListWorkspaces(WorkspaceTestCase):
    """Tests for GET /backend/workspaces."""

    def test_list_returns_all_user_workspaces(self):
        """Test listing all workspaces the user has access to."""
        data = self.get('/api/workspaces', **self.auth_headers())
        self.assertStatus(200)
        self.assertEqual(len(data), 2)  # User is member of 2 workspaces

    def test_list_without_auth_returns_401(self):
        """Test that listing workspaces without authentication fails."""
        self.get('/api/workspaces')
        self.assertStatus(401)


# =============================================================================
# Get Current Workspace Tests
# =============================================================================


class TestGetCurrentWorkspace(WorkspaceTestCase):
    """Tests for GET /backend/workspaces/current."""

    def test_get_current_workspace_success(self):
        """Test getting current workspace details."""
        data = self.get('/api/workspaces/current', **self.auth_headers())
        self.assertStatus(200)
        self.assertEqual(data['id'], self.workspace.id)
        self.assertEqual(data['name'], self.workspace_name)

    def test_get_current_workspace_includes_user_role(self):
        """GET /current should include user_role in the response."""
        data = self.get('/api/workspaces/current', **self.auth_headers())
        self.assertStatus(200)
        self.assertEqual(data['user_role'], 'owner')

    def test_get_current_workspace_without_auth_fails(self):
        """Test that getting current workspace without authentication fails."""
        self.get('/api/workspaces/current')
        self.assertStatus(401)

    def test_get_current_workspace_returns_404_when_not_a_member(self):
        """A user with current_workspace_id set but no membership should get 404."""
        from common.auth import create_access_token

        user = UserFactory(current_workspace=self.workspace)
        token = create_access_token(user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        self.get('/api/workspaces/current', **headers)
        self.assertStatus(404)


# =============================================================================
# Update Current Workspace Tests
# =============================================================================


class TestUpdateCurrentWorkspace(WorkspaceTestCase):
    """Tests for PUT /backend/workspaces/current."""

    def test_update_workspace_as_owner_success(self):
        """Test updating workspace name as owner."""
        payload = {'name': 'Updated Workspace Name'}
        data = self.put('/api/workspaces/current', payload, **self.auth_headers())
        self.assertStatus(200)
        self.assertEqual(data['name'], 'Updated Workspace Name')

    def test_update_workspace_as_admin_success(self):
        """Test updating workspace name as admin."""
        self.admin_user.current_workspace = self.workspace
        self.admin_user.save()

        token = self.create_token_for_user(self.admin_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        payload = {'name': 'Admin Updated Name'}
        data = self.put('/api/workspaces/current', payload, **headers)
        self.assertStatus(200)
        self.assertEqual(data['name'], 'Admin Updated Name')

    def test_update_workspace_as_member_fails(self):
        """Test that member cannot update workspace."""
        self.member_user.current_workspace = self.workspace
        self.member_user.save()

        token = self.create_token_for_user(self.member_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        payload = {'name': 'Should Not Work'}
        self.put('/api/workspaces/current', payload, **headers)
        self.assertStatus(403)

    def test_update_workspace_response_includes_user_role(self):
        """PUT /current should include user_role in the response."""
        payload = {'name': 'Updated Name'}
        data = self.put('/api/workspaces/current', payload, **self.auth_headers())
        self.assertStatus(200)
        self.assertEqual(data['user_role'], 'owner')

    def test_update_workspace_without_auth_fails(self):
        """Test that updating workspace without authentication fails."""
        payload = {'name': 'Should Not Work'}
        self.put('/api/workspaces/current', payload)
        self.assertStatus(401)

    def create_token_for_user(self, user):
        """Helper to create JWT token for a user."""
        from common.auth import create_access_token

        return create_access_token(user)


# =============================================================================
# Switch Workspace Tests
# =============================================================================


class TestSwitchWorkspace(WorkspaceTestCase):
    """Tests for POST /backend/workspaces/{workspace_id}/switch."""

    def test_switch_workspace_success(self):
        """Test switching to another workspace."""
        data = self.post(f'/api/workspaces/{self.other_workspace.id}/switch', {}, **self.auth_headers())
        self.assertStatus(200)
        self.assertIn('message', data)

        # Verify user's current workspace was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.current_workspace_id, self.other_workspace.id)

    def test_switch_to_workspace_without_access_fails(self):
        """Test that switching to workspace without access fails."""
        # Create a workspace the user is not a member of
        forbidden_workspace = WorkspaceFactory(name='Forbidden Workspace')

        self.post(f'/api/workspaces/{forbidden_workspace.id}/switch', {}, **self.auth_headers())
        self.assertStatus(404)

    def test_switch_workspace_without_auth_fails(self):
        """Test that switching workspace without authentication fails."""
        self.post(f'/api/workspaces/{self.other_workspace.id}/switch', {})
        self.assertStatus(401)


# =============================================================================
# List Workspace Members Tests
# =============================================================================


class TestListWorkspaceMembers(WorkspaceTestCase):
    """Tests for GET /backend/workspaces/{workspace_id}/members."""

    def test_list_members_success(self):
        """Test listing all members in workspace."""
        data = self.get(f'/api/workspaces/{self.workspace.id}/members', **self.auth_headers())
        self.assertStatus(200)
        self.assertEqual(len(data), 4)  # owner, admin, member, viewer

    def test_list_members_ordered_by_role(self):
        """Test that members are ordered by role (alphabetically, then email)."""
        data = self.get(f'/api/workspaces/{self.workspace.id}/members', **self.auth_headers())
        self.assertStatus(200)
        # Ordering is alphabetical descending on role name (viewer > owner > member > admin)
        roles = [m['role'] for m in data]
        # Should be in descending alphabetical order
        self.assertEqual(roles, sorted(roles, reverse=True))

    def test_list_members_without_access_fails(self):
        """Test that listing members without workspace access fails."""
        # Create a user who is not a member of the workspace
        non_member = UserFactory(current_workspace=None)
        token = self.create_token_for_user(non_member)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        self.get(f'/api/workspaces/{self.workspace.id}/members', **headers)
        self.assertStatus(404)

    def test_list_members_without_auth_fails(self):
        """Test that listing members without authentication fails."""
        self.get(f'/api/workspaces/{self.workspace.id}/members')
        self.assertStatus(401)

    def create_token_for_user(self, user):
        """Helper to create JWT token for a user."""
        from common.auth import create_access_token

        return create_access_token(user)


# =============================================================================
# Add Member to Workspace Tests
# =============================================================================


class TestAddMemberToWorkspace(WorkspaceTestCase):
    """Tests for POST /backend/workspaces/{workspace_id}/members/add."""

    def test_add_new_user_as_member(self):
        """Test adding a completely new user to workspace."""
        initial_member_count = WorkspaceMember.objects.filter(workspace_id=self.workspace.id).count()

        payload = {
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'full_name': 'New User',
            'role': 'member',
        }
        data = self.post(f'/api/workspaces/{self.workspace.id}/members/add', payload, **self.auth_headers())

        self.assertStatus(201)
        self.assertTrue(data['is_new_user'])
        self.assertIn('user_id', data)

        # Verify membership was created
        self.assertEqual(
            WorkspaceMember.objects.filter(workspace_id=self.workspace.id).count(),
            initial_member_count + 1,
        )

    def test_add_existing_user_as_member(self):
        """Test adding an existing user to workspace."""
        UserFactory(email='existing@example.com')

        initial_member_count = WorkspaceMember.objects.filter(workspace_id=self.workspace.id).count()

        payload = {
            'email': 'existing@example.com',
            'password': 'ignored123',
            'full_name': 'Existing User',
            'role': 'viewer',
        }
        data = self.post(f'/api/workspaces/{self.workspace.id}/members/add', payload, **self.auth_headers())

        self.assertStatus(201)
        self.assertFalse(data['is_new_user'])

        # Verify membership was created
        self.assertEqual(
            WorkspaceMember.objects.filter(workspace_id=self.workspace.id).count(),
            initial_member_count + 1,
        )

    def test_add_already_member_fails(self):
        """Test that adding a user who is already a member fails."""
        payload = {
            'email': 'admin@example.com',
            'password': 'password123',
            'full_name': 'Admin User',
            'role': 'member',
        }
        self.post(f'/api/workspaces/{self.workspace.id}/members/add', payload, **self.auth_headers())
        self.assertStatus(400)

    def test_add_member_as_admin_succeeds(self):
        """Test that admin can add members."""
        self.admin_user.current_workspace = self.workspace
        self.admin_user.save()

        token = self.create_token_for_user(self.admin_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        payload = {
            'email': 'byadmin@example.com',
            'password': 'pass1234',  # Must be at least 8 characters
            'role': 'member',
        }
        self.post(f'/api/workspaces/{self.workspace.id}/members/add', payload, **headers)
        self.assertStatus(201)

    def test_add_member_as_member_fails(self):
        """Test that regular member cannot add new members."""
        self.member_user.current_workspace = self.workspace
        self.member_user.save()

        token = self.create_token_for_user(self.member_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        payload = {
            'email': 'shouldfail@example.com',
            'password': 'pass1234',  # Must be at least 8 characters
            'role': 'viewer',
        }
        self.post(f'/api/workspaces/{self.workspace.id}/members/add', payload, **headers)
        self.assertStatus(403)

    def test_add_existing_user_without_password_succeeds(self):
        """Existing user can be added without providing a password."""
        UserFactory(email='nopwd@example.com')
        payload = {'email': 'nopwd@example.com', 'role': 'viewer'}
        data = self.post(f'/api/workspaces/{self.workspace.id}/members/add', payload, **self.auth_headers())
        self.assertStatus(201)
        self.assertFalse(data['is_new_user'])

    def test_add_existing_user_does_not_change_their_current_workspace(self):
        """Adding an existing user to a workspace does not change their current_workspace."""
        existing = UserFactory(email='e@example.com')
        original_ws = WorkspaceFactory(name='Original')
        existing.current_workspace = original_ws
        existing.save()

        payload = {'email': 'e@example.com', 'role': 'viewer'}
        self.post(f'/api/workspaces/{self.workspace.id}/members/add', payload, **self.auth_headers())
        self.assertStatus(201)

        existing.refresh_from_db()
        self.assertEqual(existing.current_workspace, original_ws)

    def test_add_new_user_without_password_fails(self):
        """New user cannot be created without a password."""
        payload = {'email': 'brand_new@example.com', 'role': 'member'}
        data = self.post(f'/api/workspaces/{self.workspace.id}/members/add', payload, **self.auth_headers())
        self.assertStatus(400)
        self.assertIn('Password', data['detail'])

    def test_add_member_without_auth_fails(self):
        """Test that adding member without authentication fails."""
        payload = {
            'email': 'test@example.com',
            'password': 'password123',
            'role': 'viewer',
        }
        self.post(f'/api/workspaces/{self.workspace.id}/members/add', payload)
        self.assertStatus(401)

    def create_token_for_user(self, user):
        """Helper to create JWT token for a user."""
        from common.auth import create_access_token

        return create_access_token(user)


# =============================================================================
# Update Member Role Tests
# =============================================================================


class TestUpdateMemberRole(WorkspaceTestCase):
    """Tests for PUT /backend/workspaces/{workspace_id}/members/{member_user_id}/role."""

    def test_update_role_as_owner_success(self):
        """Test updating member role as owner."""
        payload = {'role': 'viewer'}
        data = self.put(
            f'/api/workspaces/{self.workspace.id}/members/{self.member_user.id}/role', payload, **self.auth_headers()
        )
        self.assertStatus(200)
        self.assertEqual(data['new_role'], 'viewer')

    def test_update_own_role_fails(self):
        """Test that updating your own role fails."""
        payload = {'role': 'admin'}
        self.put(f'/api/workspaces/{self.workspace.id}/members/{self.user.id}/role', payload, **self.auth_headers())
        self.assertStatus(400)

    def test_update_owner_role_fails(self):
        """Test that changing owner role fails."""
        payload = {'role': 'admin'}
        self.put(f'/api/workspaces/{self.workspace.id}/members/{self.user.id}/role', payload, **self.auth_headers())
        self.assertStatus(400)

    def test_admin_cannot_update_other_admin(self):
        """Test that admin cannot update another admin's role."""
        # Promote member_user to admin
        member = WorkspaceMember.objects.get(
            workspace_id=self.workspace.id,
            user_id=self.member_user.id,
        )
        member.role = 'admin'
        member.save()

        self.admin_user.current_workspace = self.workspace
        self.admin_user.save()

        token = self.create_token_for_user(self.admin_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        payload = {'role': 'member'}
        self.put(f'/api/workspaces/{self.workspace.id}/members/{self.member_user.id}/role', payload, **headers)
        self.assertStatus(403)

    def test_update_role_as_member_fails(self):
        """Test that regular member cannot update roles."""
        self.member_user.current_workspace = self.workspace
        self.member_user.save()

        token = self.create_token_for_user(self.member_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        payload = {'role': 'viewer'}
        self.put(f'/api/workspaces/{self.workspace.id}/members/{self.viewer_user.id}/role', payload, **headers)
        self.assertStatus(403)

    def create_token_for_user(self, user):
        """Helper to create JWT token for a user."""
        from common.auth import create_access_token

        return create_access_token(user)


# =============================================================================
# Remove Member from Workspace Tests
# =============================================================================


class TestRemoveMemberFromWorkspace(WorkspaceTestCase):
    """Tests for DELETE /backend/workspaces/{workspace_id}/members/{member_user_id}."""

    def test_remove_member_as_owner_success(self):
        """Test removing a member as owner."""
        initial_count = WorkspaceMember.objects.filter(workspace_id=self.workspace.id).count()

        self.delete(f'/api/workspaces/{self.workspace.id}/members/{self.viewer_user.id}', **self.auth_headers())
        self.assertStatus(204)

        self.assertEqual(
            WorkspaceMember.objects.filter(workspace_id=self.workspace.id).count(),
            initial_count - 1,
        )

    def test_remove_member_clears_current_workspace(self):
        """Test that removing a member clears their current_workspace_id if it points to this workspace."""
        self.viewer_user.current_workspace = self.workspace
        self.viewer_user.save()

        self.delete(f'/api/workspaces/{self.workspace.id}/members/{self.viewer_user.id}', **self.auth_headers())
        self.assertStatus(204)

        self.viewer_user.refresh_from_db()
        self.assertIsNone(self.viewer_user.current_workspace_id)

    def test_remove_member_switches_to_other_workspace(self):
        """Test that removed member is switched to another workspace if available."""
        other_ws = WorkspaceFactory(name='Other WS')
        WorkspaceMemberFactory(workspace=other_ws, user=self.viewer_user, role='member')

        self.viewer_user.current_workspace = self.workspace
        self.viewer_user.save()

        self.delete(f'/api/workspaces/{self.workspace.id}/members/{self.viewer_user.id}', **self.auth_headers())
        self.assertStatus(204)

        self.viewer_user.refresh_from_db()
        self.assertEqual(self.viewer_user.current_workspace_id, other_ws.id)

    def test_remove_member_preserves_current_workspace_if_different(self):
        """Test that removing a member doesn't change their current_workspace if it points elsewhere."""
        other_ws = WorkspaceFactory(name='Other WS')
        WorkspaceMemberFactory(workspace=other_ws, user=self.viewer_user, role='member')

        self.viewer_user.current_workspace = other_ws
        self.viewer_user.save()

        self.delete(f'/api/workspaces/{self.workspace.id}/members/{self.viewer_user.id}', **self.auth_headers())
        self.assertStatus(204)

        self.viewer_user.refresh_from_db()
        self.assertEqual(self.viewer_user.current_workspace_id, other_ws.id)

    def test_remove_yourself_fails(self):
        """Test that removing yourself fails."""
        self.delete(f'/api/workspaces/{self.workspace.id}/members/{self.user.id}', **self.auth_headers())
        self.assertStatus(400)

    def test_remove_owner_fails(self):
        """Test that removing owner fails."""
        self.delete(f'/api/workspaces/{self.workspace.id}/members/{self.user.id}', **self.auth_headers())
        self.assertStatus(400)

    def test_admin_cannot_remove_other_admin(self):
        """Test that admin cannot remove another admin."""
        # Promote member_user to admin
        member = WorkspaceMember.objects.get(
            workspace_id=self.workspace.id,
            user_id=self.member_user.id,
        )
        member.role = 'admin'
        member.save()

        self.admin_user.current_workspace = self.workspace
        self.admin_user.save()

        token = self.create_token_for_user(self.admin_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        self.delete(f'/api/workspaces/{self.workspace.id}/members/{self.member_user.id}', **headers)
        self.assertStatus(403)

    def test_remove_member_as_member_fails(self):
        """Test that regular member cannot remove other members."""
        self.member_user.current_workspace = self.workspace
        self.member_user.save()

        token = self.create_token_for_user(self.member_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        self.delete(f'/api/workspaces/{self.workspace.id}/members/{self.viewer_user.id}', **headers)
        self.assertStatus(403)

    def create_token_for_user(self, user):
        """Helper to create JWT token for a user."""
        from common.auth import create_access_token

        return create_access_token(user)


# =============================================================================
# Leave Workspace Tests
# =============================================================================


class TestLeaveWorkspace(WorkspaceTestCase):
    """Tests for POST /backend/workspaces/{workspace_id}/members/leave."""

    def test_leave_workspace_as_member_success(self):
        """Test leaving workspace as member (must have another workspace)."""
        other_workspace = WorkspaceFactory(name='Member Other Workspace')
        WorkspaceMemberFactory(
            workspace=other_workspace,
            user=self.member_user,
            role='member',
        )
        self.member_user.current_workspace = self.workspace
        self.member_user.save()

        token = self.create_token_for_user(self.member_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        initial_count = WorkspaceMember.objects.filter(workspace_id=self.workspace.id).count()

        self.post(f'/api/workspaces/{self.workspace.id}/members/leave', {}, **headers)
        self.assertStatus(200)

        self.assertEqual(
            WorkspaceMember.objects.filter(workspace_id=self.workspace.id).count(),
            initial_count - 1,
        )

        self.member_user.refresh_from_db()
        self.assertEqual(self.member_user.current_workspace_id, other_workspace.id)

    def test_leave_only_workspace_as_member_fails(self):
        """Test that member cannot leave their only workspace."""
        self.member_user.current_workspace = self.workspace
        self.member_user.save()

        token = self.create_token_for_user(self.member_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        self.post(f'/api/workspaces/{self.workspace.id}/members/leave', {}, **headers)
        self.assertStatus(400)

    def test_leave_workspace_as_owner_fails(self):
        """Test that owner cannot leave workspace."""
        self.post(f'/api/workspaces/{self.workspace.id}/members/leave', {}, **self.auth_headers())
        self.assertStatus(400)

    def test_leave_workspace_without_auth_fails(self):
        """Test that leaving workspace without authentication fails."""
        self.post(f'/api/workspaces/{self.workspace.id}/members/leave', {})
        self.assertStatus(401)

    def create_token_for_user(self, user):
        """Helper to create JWT token for a user."""
        from common.auth import create_access_token

        return create_access_token(user)


# =============================================================================
# Reset Member Password Tests
# =============================================================================


class TestResetMemberPassword(WorkspaceTestCase):
    """Tests for PUT /backend/workspaces/{workspace_id}/members/{user_id}/reset-password."""

    def test_reset_password_as_owner_success(self):
        """Test resetting member password as owner."""
        payload = {'new_password': 'newpassword123'}
        data = self.put(
            f'/api/workspaces/{self.workspace.id}/members/{self.member_user.id}/reset-password',
            payload,
            **self.auth_headers(),
        )
        self.assertStatus(200)
        self.assertIn('message', data)

        # Verify password was actually changed
        self.member_user.refresh_from_db()
        self.assertTrue(self.member_user.check_password('newpassword123'))

    def test_reset_own_password_fails(self):
        """Test that resetting your own password fails."""
        payload = {'new_password': 'newpassword123'}
        self.put(
            f'/api/workspaces/{self.workspace.id}/members/{self.user.id}/reset-password', payload, **self.auth_headers()
        )
        self.assertStatus(400)

    def test_reset_owner_password_fails(self):
        """Test that resetting owner's password fails."""
        payload = {'new_password': 'newpassword123'}
        self.put(
            f'/api/workspaces/{self.workspace.id}/members/{self.user.id}/reset-password', payload, **self.auth_headers()
        )
        self.assertStatus(400)

    def test_admin_cannot_reset_other_admin_password(self):
        """Test that admin cannot reset another admin's password."""
        # Make the target user an admin
        member = WorkspaceMember.objects.get(
            workspace_id=self.workspace.id,
            user_id=self.member_user.id,
        )
        member.role = 'admin'
        member.save()

        self.admin_user.current_workspace = self.workspace
        self.admin_user.save()

        token = self.create_token_for_user(self.admin_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        payload = {'new_password': 'newpassword123'}
        self.put(
            f'/api/workspaces/{self.workspace.id}/members/{self.member_user.id}/reset-password', payload, **headers
        )
        self.assertStatus(403)

    def test_reset_password_as_member_fails(self):
        """Test that regular member cannot reset passwords."""
        self.member_user.current_workspace = self.workspace
        self.member_user.save()

        token = self.create_token_for_user(self.member_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        payload = {'new_password': 'newpassword123'}
        self.put(
            f'/api/workspaces/{self.workspace.id}/members/{self.viewer_user.id}/reset-password', payload, **headers
        )
        self.assertStatus(403)

    def create_token_for_user(self, user):
        """Helper to create JWT token for a user."""
        from common.auth import create_access_token

        return create_access_token(user)


# =============================================================================
# Create Workspace Tests
# =============================================================================


class TestCreateWorkspace(APIClientMixin, TestCase):
    """Tests for POST /api/workspaces/."""

    def setUp(self):
        """Set up test data."""
        APIClientMixin.setUp(self)
        self.user = UserFactory()
        from common.auth import create_access_token

        self.auth_token = create_access_token(self.user)

    def auth_headers(self):
        """Get auth headers for authenticated requests."""
        return {'HTTP_AUTHORIZATION': f'Bearer {self.auth_token}'}

    def test_create_workspace_returns_201(self):
        """Test that creating workspace returns 201 with WorkspaceOut."""
        payload = {'name': 'New Workspace'}
        data = self.post('/api/workspaces/', payload, **self.auth_headers())
        self.assertStatus(201)
        self.assertEqual(data['name'], 'New Workspace')
        self.assertEqual(data['user_role'], 'owner')
        self.assertIn('id', data)

    def test_create_workspace_sets_current_workspace(self):
        """Test that creating workspace sets user.current_workspace."""
        payload = {'name': 'New Workspace'}
        self.post('/api/workspaces/', payload, **self.auth_headers())
        self.assertStatus(201)

        self.user.refresh_from_db()
        self.assertEqual(self.user.current_workspace.name, 'New Workspace')

    def test_create_workspace_without_auth_fails(self):
        """Test that creating workspace without authentication fails."""
        payload = {'name': 'New Workspace'}
        self.post('/api/workspaces/', payload)
        self.assertStatus(401)

    def test_create_workspace_with_blank_name_fails(self):
        """Test that creating a workspace with blank name returns 422."""
        payload = {'name': '   '}
        self.post('/api/workspaces/', payload, **self.auth_headers())
        self.assertStatus(422)

    def test_create_workspace_with_empty_name_fails(self):
        """Test that creating a workspace with empty name returns 422."""
        payload = {'name': ''}
        self.post('/api/workspaces/', payload, **self.auth_headers())
        self.assertStatus(422)


# =============================================================================
# Delete Workspace Tests
# =============================================================================


class TestDeleteWorkspace(APIClientMixin, AuthMixin, TestCase):
    """Tests for DELETE /api/workspaces/{workspace_id}."""

    def setUp(self):
        """Set up test data."""
        APIClientMixin.setUp(self)
        AuthMixin.setUp(self)

        from workspaces.services import WorkspaceService

        self.second_workspace = WorkspaceService.create_workspace(
            user=self.user, name='Second Workspace', create_demo=False
        )

    def test_delete_workspace_returns_204(self):
        """Test that deleting workspace returns 204."""
        ws_id = self.second_workspace.id
        self.delete(f'/api/workspaces/{ws_id}', **self.auth_headers())
        self.assertStatus(204)

    def test_delete_workspace_as_owner_succeeds(self):
        """Test that owner can delete workspace."""
        ws_id = self.second_workspace.id
        self.delete(f'/api/workspaces/{ws_id}', **self.auth_headers())
        self.assertStatus(204)

        self.assertFalse(Workspace.objects.filter(id=ws_id).exists())

    def test_delete_workspace_as_non_owner_fails(self):
        """Test that non-owner cannot delete workspace."""
        non_owner = UserFactory(current_workspace=self.second_workspace)
        WorkspaceMemberFactory(
            workspace=self.second_workspace,
            user=non_owner,
            role='admin',
        )

        from common.auth import create_access_token

        token = create_access_token(non_owner)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        self.delete(f'/api/workspaces/{self.second_workspace.id}', **headers)
        self.assertStatus(403)

    def test_delete_nonexistent_workspace_returns_404(self):
        """Test that deleting nonexistent workspace returns 404."""
        self.delete('/api/workspaces/99999', **self.auth_headers())
        self.assertStatus(404)

    def test_delete_non_member_returns_404(self):
        """Test that deleting a workspace where user is not a member returns 404."""
        from common.auth import create_access_token

        non_member = UserFactory()
        token = create_access_token(non_member)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        self.delete(f'/api/workspaces/{self.second_workspace.id}', **headers)
        self.assertStatus(404)

    def test_delete_workspace_without_auth_fails(self):
        """Test that deleting workspace without authentication fails."""
        self.delete(f'/api/workspaces/{self.second_workspace.id}')
        self.assertStatus(401)

    def test_delete_only_workspace_returns_400(self):
        """Test that deleting the user's only workspace returns 400."""
        # Use a user with only one workspace
        single_ws_user = UserFactory(current_workspace=self.workspace)
        WorkspaceMemberFactory(
            workspace=self.workspace,
            user=single_ws_user,
            role='owner',
        )

        from common.auth import create_access_token

        token = create_access_token(single_ws_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        # Delete the second workspace first (owned by self.user, not single_ws_user)
        self.delete(f'/api/workspaces/{self.second_workspace.id}', **self.auth_headers())
        self.assertStatus(204)

        # Now single_ws_user only has self.workspace — deleting it should fail
        self.delete(f'/api/workspaces/{self.workspace.id}', **headers)
        self.assertStatus(400)

    def test_delete_workspace_where_member_has_no_other_workspace_returns_400(self):
        """Test that deleting a workspace where a member has no other workspace returns 400."""
        # Create a member who only belongs to second_workspace
        sole_member = UserFactory(current_workspace=self.second_workspace)
        WorkspaceMemberFactory(workspace=self.second_workspace, user=sole_member, role='member')
        # sole_member has no other workspace — deletion must be blocked
        self.delete(f'/api/workspaces/{self.second_workspace.id}', **self.auth_headers())
        self.assertStatus(400)
        # Workspace must still exist
        self.assertTrue(Workspace.objects.filter(id=self.second_workspace.id).exists())


# =============================================================================
# Leave Workspace Edge Case Tests
# =============================================================================


class TestLeaveWorkspaceCurrentWorkspace(WorkspaceTestCase):
    """Tests for leave workspace affecting current_workspace."""

    def test_leave_current_workspace_switches_to_next(self):
        """Test that leaving current workspace switches to another available one."""
        ws_to_leave = WorkspaceFactory(name='To Leave')
        WorkspaceMemberFactory(workspace=ws_to_leave, user=self.member_user, role='member')

        token = self.create_token_for_user(self.member_user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        self.member_user.current_workspace = ws_to_leave
        self.member_user.save()

        self.post(f'/api/workspaces/{ws_to_leave.id}/members/leave', {}, **headers)
        self.assertStatus(200)

        self.member_user.refresh_from_db()
        self.assertIsNotNone(self.member_user.current_workspace)
        self.assertNotEqual(self.member_user.current_workspace_id, ws_to_leave.id)

    def create_token_for_user(self, user):
        """Helper to create JWT token for a user."""
        from common.auth import create_access_token

        return create_access_token(user)


class TestWorkspaceJWTAuth400(APIClientMixin, TestCase):
    """Tests for WorkspaceJWTAuth returning 400 when no workspace is active."""

    def setUp(self):
        """Set up test data."""
        APIClientMixin.setUp(self)

    def test_workspace_scoped_endpoint_returns_400_without_active_workspace(self):
        """A valid JWT with no current_workspace_id should get 400 on workspace-scoped endpoints."""
        from common.auth import create_access_token
        from common.tests.factories import UserFactory

        user = UserFactory(current_workspace=None)
        token = create_access_token(user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        self.get('/api/workspaces/current', **headers)
        self.assertStatus(400)

    def test_workspace_scoped_endpoints_return_400_without_active_workspace(self):
        """Multiple workspace-scoped endpoints should return 400 when user has no current_workspace."""
        from common.auth import create_access_token
        from common.tests.factories import UserFactory

        user = UserFactory(current_workspace=None)
        token = create_access_token(user)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        endpoints = [
            '/api/workspaces/current',
            '/api/budget-accounts',
            '/api/currencies',
            '/api/transactions',
            '/api/categories',
        ]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                self.get(endpoint, **headers)
                self.assertStatus(400)
