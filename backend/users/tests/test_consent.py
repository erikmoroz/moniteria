"""Tests for GDPR consent management."""

from django.test import TestCase

from common.tests.mixins import AuthMixin
from users.models import ConsentType, UserConsent


class ConsentTests(AuthMixin, TestCase):
    """Tests for GDPR consent management."""

    def test_register_creates_both_consents(self):
        """Registration should create consent records for TOS and privacy policy."""
        response = self.client.post(
            '/api/auth/register',
            {
                'email': 'newuser@test.com',
                'password': 'testpass123',
                'workspace_name': 'Test',
                'accepted_terms_version': '1.0',
                'accepted_privacy_version': '1.0',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)

        from django.contrib.auth import get_user_model

        user = get_user_model().objects.get(email='newuser@test.com')
        consents = UserConsent.objects.filter(user=user, withdrawn_at__isnull=True)
        consent_types = set(consents.values_list('consent_type', flat=True))
        self.assertEqual(consent_types, {ConsentType.TERMS_OF_SERVICE, ConsentType.PRIVACY_POLICY})

    def test_register_without_consent_fields_rejected(self):
        """Registration without consent fields should return 422."""
        response = self.client.post(
            '/api/auth/register',
            {
                'email': 'newuser@test.com',
                'password': 'testpass123',
                'workspace_name': 'Test',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 422)

    def test_list_active_consents(self):
        """GET /users/me/consents should return active consents only."""
        UserConsent.objects.create(user=self.user, consent_type='terms_of_service', version='1.0')
        UserConsent.objects.create(user=self.user, consent_type='privacy_policy', version='1.0')

        response = self.client.get('/api/users/me/consents', **self.auth_headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_withdraw_consent(self):
        """DELETE /users/me/consents/{type} should set withdrawn_at."""
        UserConsent.objects.create(user=self.user, consent_type='terms_of_service', version='1.0')

        response = self.client.delete('/api/users/me/consents/terms_of_service', **self.auth_headers())
        self.assertEqual(response.status_code, 200)

        consent = UserConsent.objects.get(user=self.user, consent_type='terms_of_service')
        self.assertIsNotNone(consent.withdrawn_at)

    def test_withdraw_nonexistent_consent_returns_404(self):
        """Withdrawing consent that doesn't exist should return 404."""
        response = self.client.delete('/api/users/me/consents/terms_of_service', **self.auth_headers())
        self.assertEqual(response.status_code, 404)

    def test_grant_consent_invalid_type_returns_422(self):
        """Granting consent with invalid type should return 422 (schema validation)."""
        response = self.client.post(
            '/api/users/me/consents',
            {
                'consent_type': 'invalid_type',
                'version': '1.0',
            },
            content_type='application/json',
            **self.auth_headers(),
        )
        self.assertEqual(response.status_code, 422)

    def test_grant_consent_records_ip_address(self):
        """Granting consent should record the client's IP address."""
        response = self.client.post(
            '/api/users/me/consents',
            {
                'consent_type': 'terms_of_service',
                'version': '1.0',
            },
            content_type='application/json',
            **self.auth_headers(),
        )
        self.assertEqual(response.status_code, 201)

        consent = UserConsent.objects.get(user=self.user, consent_type='terms_of_service')
        self.assertIsNotNone(consent.ip_address)
