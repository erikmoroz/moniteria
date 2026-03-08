import { Link } from 'react-router-dom';

export default function TermsPage() {
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
            <h1 className="text-3xl font-bold text-gray-900">Terms of Service</h1>
            <p className="mt-2 text-sm text-gray-500">Effective date: 2025-01-01 &middot; Version 1.0</p>
          </div>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">1. Acceptance of Terms</h2>
            <p className="text-gray-700">
              By registering for and using Monie, you agree to be bound by these Terms of Service.
              If you do not agree to these terms, please do not use the service.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">2. Service Description</h2>
            <p className="text-gray-700">
              Monie is a personal finance tracking application that provides:
            </p>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li>Multi-currency budget tracking</li>
              <li>Period-based budgeting with categories</li>
              <li>Transaction management (income and expenses)</li>
              <li>Planned transaction scheduling</li>
              <li>Currency exchange recording</li>
              <li>Collaborative workspace features with role-based access</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">3. Account Registration</h2>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li>You must provide a valid email address to register</li>
              <li>You are responsible for maintaining the security of your password</li>
              <li>You must notify us immediately of any unauthorized access to your account</li>
              <li>One account per person; do not share account credentials</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">4. Acceptable Use</h2>
            <p className="text-gray-700">You agree to use Monie only for:</p>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li>Personal or business finance tracking</li>
              <li>Legitimate budgeting and financial planning</li>
            </ul>
            <p className="text-gray-700 mt-2">You agree NOT to:</p>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li>Use the service for any illegal activities</li>
              <li>Attempt to gain unauthorized access to other accounts or systems</li>
              <li>Use automated tools to scrape or abuse the API</li>
              <li>Reverse engineer or attempt to extract source code</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">5. Data &amp; Privacy</h2>
            <p className="text-gray-700">
              Your use of Monie is also governed by our{' '}
              <Link to="/privacy" className="text-blue-600 hover:underline">Privacy Policy</Link>,
              which is incorporated into these Terms by reference. Please read it carefully.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">6. Workspace Collaboration</h2>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li>Workspace owners are responsible for managing member access and roles</li>
              <li>All members of a workspace can view data within that workspace (based on their role)</li>
              <li>Owners must resolve shared workspace memberships before deleting their account</li>
              <li>Members may leave a workspace at any time</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">7. Account Termination</h2>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li>You may delete your account at any time from <em>Profile Settings &rarr; Account</em></li>
              <li>Account deletion is permanent and irreversible</li>
              <li>We may suspend or terminate accounts for violations of these Terms</li>
              <li>We will provide notice before termination when possible</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">8. Intellectual Property</h2>
            <ul className="list-disc list-inside text-gray-700 space-y-1 ml-4">
              <li>You own your financial data entered into Monie</li>
              <li>You may export your data at any time</li>
              <li>The Monie software, design, and branding are owned by [Your Company Name]</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">9. Limitation of Liability</h2>
            <p className="text-gray-700">
              Monie is provided &ldquo;as is&rdquo; without warranty of any kind. We are not liable for any indirect,
              incidental, special, or consequential damages arising from your use of the service.
              Our total liability shall not exceed the amount you paid for the service in the past
              12 months.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">10. Governing Law</h2>
            <p className="text-gray-700">
              These Terms are governed by the laws of [Your Jurisdiction]. Any disputes shall be
              resolved in the courts of [Your Jurisdiction].
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold text-gray-900">11. Contact</h2>
            <p className="text-gray-700">
              For questions about these Terms, contact us at:{' '}
              <strong>[Your Company Name]</strong>,{' '}
              <a href="mailto:your-email@example.com" className="text-blue-600 hover:underline">
                [your-email@example.com]
              </a>
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
