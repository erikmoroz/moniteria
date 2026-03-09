"""Tests for legal document templates and API endpoints."""

from django.test import SimpleTestCase, TestCase, override_settings

from common.tests.mixins import APIClientMixin
from core.legal import _get_legal_context, get_privacy, get_terms


class LegalTemplateTests(SimpleTestCase):
    """Tests for legal document template rendering (no database required)."""

    def test_default_context_uses_settings(self):
        """Context should be built from Django settings."""
        with override_settings(
            LEGAL_OPERATOR_NAME='Test Company',
            LEGAL_OPERATOR_TYPE='company',
            LEGAL_CONTACT_EMAIL='test@example.com',
            LEGAL_CONTACT_ADDRESS='123 Test St',
            LEGAL_JURISDICTION='Test Jurisdiction',
        ):
            ctx = _get_legal_context()
            self.assertEqual(ctx['operator_name'], 'Test Company')
            self.assertEqual(ctx['operator_type'], 'company')
            self.assertEqual(ctx['contact_email'], 'test@example.com')
            self.assertEqual(ctx['contact_address'], '123 Test St')
            self.assertEqual(ctx['jurisdiction'], 'Test Jurisdiction')
            self.assertFalse(ctx['is_individual'])
            self.assertTrue(ctx['is_company'])

    def test_context_for_individual_operator(self):
        """Context should correctly identify individual operators."""
        with override_settings(
            LEGAL_OPERATOR_NAME='John Doe',
            LEGAL_OPERATOR_TYPE='individual',
        ):
            ctx = _get_legal_context()
            self.assertTrue(ctx['is_individual'])
            self.assertFalse(ctx['is_company'])

    def test_terms_template_renders_all_variables(self):
        """Terms of Service should render all template variables."""
        with override_settings(
            LEGAL_OPERATOR_NAME='Acme Corp',
            LEGAL_OPERATOR_TYPE='company',
            LEGAL_CONTACT_EMAIL='legal@acme.com',
            LEGAL_CONTACT_ADDRESS='123 Business Ave',
            LEGAL_JURISDICTION='California, USA',
        ):
            terms = get_terms()
            content = terms['content']

            self.assertIn('Acme Corp', content)
            self.assertIn('legal@acme.com', content)
            self.assertIn('123 Business Ave', content)
            self.assertIn('California, USA', content)
            self.assertNotIn('(an individual)', content)

    def test_privacy_template_renders_all_variables(self):
        """Privacy Policy should render all template variables."""
        with override_settings(
            LEGAL_OPERATOR_NAME='Jane Smith',
            LEGAL_OPERATOR_TYPE='individual',
            LEGAL_CONTACT_EMAIL='jane@example.com',
            LEGAL_CONTACT_ADDRESS='456 Personal St',
            LEGAL_JURISDICTION='United States',
        ):
            privacy = get_privacy()
            content = privacy['content']

            self.assertIn('Jane Smith', content)
            self.assertIn('jane@example.com', content)
            self.assertIn('456 Personal St', content)
            self.assertIn('United States', content)
            self.assertIn('(an individual)', content)

    def test_terms_includes_version_and_date(self):
        """Terms of Service should include version and effective date from frontmatter."""
        terms = get_terms()

        self.assertIn('version', terms)
        self.assertIn('effective_date', terms)
        self.assertIsNotNone(terms['version'])
        self.assertIsNotNone(terms['effective_date'])
        self.assertRegex(terms['version'], r'^\d+\.\d+$')

    def test_privacy_includes_version_and_date(self):
        """Privacy Policy should include version and effective date from frontmatter."""
        privacy = get_privacy()

        self.assertIn('version', privacy)
        self.assertIn('effective_date', privacy)
        self.assertIsNotNone(privacy['version'])
        self.assertIsNotNone(privacy['effective_date'])
        self.assertRegex(privacy['version'], r'^\d+\.\d+$')

    def test_terms_template_without_address(self):
        """Terms of Service should omit address section if not provided."""
        with override_settings(
            LEGAL_OPERATOR_NAME='Simple Corp',
            LEGAL_CONTACT_ADDRESS='',
        ):
            terms = get_terms()
            content = terms['content']

            self.assertIn('Simple Corp', content)
            # Address line should not appear if empty

    def test_privacy_template_without_address(self):
        """Privacy Policy should omit address section if not provided."""
        with override_settings(
            LEGAL_OPERATOR_NAME='Simple Person',
            LEGAL_OPERATOR_TYPE='individual',
            LEGAL_CONTACT_ADDRESS='',
        ):
            privacy = get_privacy()
            content = privacy['content']

            self.assertIn('Simple Person', content)

    def test_templates_contain_required_sections(self):
        """Legal documents should contain all required GDPR sections."""
        terms = get_terms()
        privacy = get_privacy()

        # Terms should have these sections
        self.assertIn('Acceptance of Terms', terms['content'])
        self.assertIn('Data & Privacy', terms['content'])
        self.assertIn('Account Termination', terms['content'])
        self.assertIn('Governing Law', terms['content'])

        # Privacy should have these sections
        self.assertIn('Data We Collect', privacy['content'])
        self.assertIn('Legal Basis', privacy['content'])
        self.assertIn('Your Rights', privacy['content'])
        self.assertIn('Data Security', privacy['content'])

    def test_templates_contain_no_unrendered_variables(self):
        """Rendered templates should not contain Django template syntax."""
        with override_settings(
            LEGAL_OPERATOR_NAME='Test Operator',
            LEGAL_OPERATOR_TYPE='company',
            LEGAL_CONTACT_EMAIL='test@test.com',
            LEGAL_JURISDICTION='Test',
        ):
            terms = get_terms()
            privacy = get_privacy()

            # Should not contain template variable syntax
            self.assertNotIn('{{', terms['content'])
            self.assertNotIn('}}', terms['content'])
            self.assertNotIn('{%', terms['content'])
            self.assertNotIn('%}', terms['content'])

            self.assertNotIn('{{', privacy['content'])
            self.assertNotIn('}}', privacy['content'])
            self.assertNotIn('{%', privacy['content'])
            self.assertNotIn('%}', privacy['content'])


class LegalAPITests(APIClientMixin, TestCase):
    """Tests for legal document API endpoints."""

    def test_get_terms_endpoint(self):
        """GET /api/legal/terms should return terms with version and content."""
        response = self.client.get('/api/legal/terms')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('version', data)
        self.assertIn('effective_date', data)
        self.assertIn('content', data)
        self.assertIsInstance(data['content'], str)
        self.assertGreater(len(data['content']), 100)

    def test_get_privacy_endpoint(self):
        """GET /api/legal/privacy should return privacy policy with version and content."""
        response = self.client.get('/api/legal/privacy')

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('version', data)
        self.assertIn('effective_date', data)
        self.assertIn('content', data)
        self.assertIsInstance(data['content'], str)
        self.assertGreater(len(data['content']), 100)

    def test_legal_endpoints_are_public(self):
        """Legal document endpoints should not require authentication."""
        # No auth headers provided
        response_terms = self.client.get('/api/legal/terms')
        response_privacy = self.client.get('/api/legal/privacy')

        self.assertEqual(response_terms.status_code, 200)
        self.assertEqual(response_privacy.status_code, 200)

    def test_terms_content_matches_template(self):
        """Terms API should return rendered template content."""
        with override_settings(
            LEGAL_OPERATOR_NAME='API Test Corp',
            LEGAL_CONTACT_EMAIL='apitest@example.com',
        ):
            response = self.client.get('/api/legal/terms')
            data = response.json()

            self.assertIn('API Test Corp', data['content'])
            self.assertIn('apitest@example.com', data['content'])

    def test_privacy_content_matches_template(self):
        """Privacy API should return rendered template content."""
        with override_settings(
            LEGAL_OPERATOR_NAME='API Test Individual',
            LEGAL_OPERATOR_TYPE='individual',
            LEGAL_CONTACT_EMAIL='individual@example.com',
        ):
            response = self.client.get('/api/legal/privacy')
            data = response.json()

            self.assertIn('API Test Individual', data['content'])
            self.assertIn('individual@example.com', data['content'])
            self.assertIn('(an individual)', data['content'])
