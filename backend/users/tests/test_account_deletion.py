"""Tests for GDPR account deletion (Right to Erasure)."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from common.tests.mixins import AuthMixin
from workspaces.models import Workspace, WorkspaceMember

User = get_user_model()


class AccountDeletionTests(AuthMixin, TestCase):
    """Tests for GDPR account deletion (Right to Erasure)."""

    def test_delete_account_success(self):
        """Solo workspace owner can delete account. User, workspace, and all data are deleted."""
        workspace_id = self.workspace.id

        response = self.client.delete(
            '/api/users/me',
            {'password': self.user_password},
            content_type='application/json',
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(id=self.user.id).exists())
        self.assertFalse(Workspace.objects.filter(id=workspace_id).exists())

    def test_delete_account_wrong_password(self):
        """Deletion with wrong password should return 401."""
        response = self.client.delete(
            '/api/users/me',
            {'password': 'wrongpassword'},
            content_type='application/json',
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 401)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_delete_account_blocked_by_shared_workspace(self):
        """Cannot delete if user owns a workspace with other members."""
        other_user = User.objects.create_user(email='other@test.com', password='pass12345')
        WorkspaceMember.objects.create(workspace=self.workspace, user=other_user, role='member')

        response = self.client.delete(
            '/api/users/me',
            {'password': self.user_password},
            content_type='application/json',
            **self.auth_headers(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_delete_removes_membership_from_others_workspace(self):
        """When deleted, user's memberships in other workspaces are removed."""
        other_owner = User.objects.create_user(email='owner@test.com', password='pass12345')
        other_ws = Workspace.objects.create(name='Other Workspace', owner=other_owner)
        WorkspaceMember.objects.create(workspace=other_ws, user=other_owner, role='owner')
        WorkspaceMember.objects.create(workspace=other_ws, user=self.user, role='member')

        self.client.delete(
            '/api/users/me',
            {'password': self.user_password},
            content_type='application/json',
            **self.auth_headers(),
        )

        # Other workspace still exists, but our membership is gone
        self.assertTrue(Workspace.objects.filter(id=other_ws.id).exists())
        self.assertFalse(WorkspaceMember.objects.filter(user_id=self.user.id).exists())

    def test_deletion_check_accurate(self):
        """Pre-deletion check returns accurate counts."""
        response = self.client.get('/api/users/me/deletion-check', **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['can_delete'])
        self.assertIn(self.workspace.name, data['solo_workspaces'])

    def test_deletion_check_blocked_when_shared_workspace(self):
        """Pre-deletion check shows blocked when user owns shared workspace."""
        other_user = User.objects.create_user(email='other@test.com', password='pass12345')
        WorkspaceMember.objects.create(workspace=self.workspace, user=other_user, role='member')

        response = self.client.get('/api/users/me/deletion-check', **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['can_delete'])
        self.assertIsNotNone(data['blocking_workspaces'])
        self.assertEqual(len(data['blocking_workspaces']), 1)
