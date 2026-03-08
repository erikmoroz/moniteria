import { Link } from 'react-router-dom';

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <div className="mb-8">
          <Link to="/login" className="text-sm text-blue-600 hover:text-blue-500">
            &larr; Back to login
          </Link>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 space-y-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Privacy Policy</h1>
            <p className="mt-2 text-sm text-gray-500">Effective date: 2025-01-01 &middot; Version 1.0</p>
          </div>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">1. Introduction</h2>
            <p className="text-gray-700">
              Monie (&ldquo;we&rdquo;, &ldquo;our&rdquo;, or &ldquo;us&rdquo;), operated by [Your Company Name], provides a personal finance
              tracking application. This Privacy Policy explains how we collect, use, and protect your personal
              data when you use Monie.
            </p>
            <p className="text-gray-700">
              By registering for Monie, you agree to the collection and use of information in accordance with
              this policy.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">2. Data We Collect</h2>
            <div className="space-y-2">
              <p className="text-gray-700 font-medium">Account data:</p>
              <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
                <li>Email address (required, used for authentication)</li>
                <li>Full name (optional)</li>
                <li>Password (stored as a secure hash — never in plain text)</li>
              </ul>
            </div>
            <div className="space-y-2">
              <p className="text-gray-700 font-medium">Financial data:</p>
              <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
                <li>Transactions (income and expense records)</li>
                <li>Budgets and categories</li>
                <li>Planned transactions</li>
                <li>Currency exchange records</li>
                <li>Period balances</li>
              </ul>
            </div>
            <div className="space-y-2">
              <p className="text-gray-700 font-medium">Technical data:</p>
              <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
                <li>IP address — stored temporarily in Redis for rate limiting only (auto-expires, typically within 60 seconds)</li>
                <li>IP address at time of consent — stored with consent records for legal audit purposes</li>
              </ul>
            </div>
            <div className="space-y-2">
              <p className="text-gray-700 font-medium">Preferences:</p>
              <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
                <li>Calendar start day preference</li>
              </ul>
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">3. How We Use Your Data</h2>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li>Providing the Monie service (personal finance tracking and budgeting)</li>
              <li>Authenticating your identity via JWT tokens</li>
              <li>Rate limiting to prevent abuse and protect the service</li>
              <li>Maintaining an audit trail of your consent (GDPR compliance)</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">4. Legal Basis (GDPR Article 6)</h2>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li><strong>Consent (Art. 6(1)(a)):</strong> You explicitly agree to our Terms of Service and Privacy Policy at registration.</li>
              <li><strong>Legitimate interest (Art. 6(1)(f)):</strong> Rate limiting and security measures to protect our service and users.</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">5. Data Retention</h2>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li>Account and financial data: retained until you delete your account</li>
              <li>Consent records: retained for legal compliance even after account deletion</li>
              <li>Rate limiting data: automatically expires (Redis TTL, typically 60 seconds)</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">6. Your Rights (GDPR)</h2>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li><strong>Right to Access:</strong> Export all your data from <em>Profile Settings &rarr; Account &rarr; Export All My Data</em></li>
              <li><strong>Right to Rectification:</strong> Update your profile from <em>Profile Settings &rarr; Profile Information</em></li>
              <li><strong>Right to Erasure:</strong> Delete your account from <em>Profile Settings &rarr; Account &rarr; Delete My Account</em></li>
              <li><strong>Right to Data Portability:</strong> Download your data in JSON format via the export feature</li>
              <li><strong>Right to Withdraw Consent:</strong> Contact us at [your-email@example.com]</li>
            </ul>
            <p className="text-gray-700">
              To exercise any rights, use the in-app features above or contact us at{' '}
              <a href="mailto:your-email@example.com" className="text-blue-600 hover:underline">
                [your-email@example.com]
              </a>.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">7. Data Sharing</h2>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li>We do not share your personal data with third parties</li>
              <li>We do not use analytics or tracking services</li>
              <li>We do not use advertising networks</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">8. Cookies &amp; Local Storage</h2>
            <p className="text-gray-700">
              We use <code className="bg-gray-100 px-1 rounded">localStorage</code> to store your authentication token.
              This is strictly functional — it allows you to stay logged in between sessions.
              We do not use tracking cookies or analytics cookies.
              No cookie consent banner is required as we use no tracking storage.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">9. Data Security</h2>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li>All data is transmitted over HTTPS/TLS</li>
              <li>Passwords are hashed using industry-standard algorithms</li>
              <li>Role-based access control for shared workspaces</li>
              <li>Rate limiting to prevent brute-force attacks</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">10. Contact</h2>
            <p className="text-gray-700">
              For privacy-related questions or to exercise your rights, contact us at:{' '}
              <strong>[Your Company Name]</strong>,{' '}
              <a href="mailto:your-email@example.com" className="text-blue-600 hover:underline">
                [your-email@example.com]
              </a>
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">11. Changes to This Policy</h2>
            <p className="text-gray-700">
              We may update this Privacy Policy when our practices change or when required by law.
              When we make significant changes, we will notify registered users via email or in-app notification.
              Continued use of Monie after changes constitutes acceptance of the updated policy.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
