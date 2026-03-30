import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { authApi } from '../api/client'

type State = 'loading' | 'success' | 'error' | 'resend' | 'resend-success'

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const [state, setState] = useState<State>('loading')
  const [resendEmail, setResendEmail] = useState('')
  const [isResending, setIsResending] = useState(false)

  useEffect(() => {
    const token = searchParams.get('token')
    if (!token) {
      setState('error')
      return
    }

    authApi
      .verifyEmail(token)
      .then(() => setState('success'))
      .catch(() => setState('error'))
  }, [searchParams])

  const handleResend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!resendEmail) return

    setIsResending(true)
    try {
      await authApi.resendVerification(resendEmail)
      setState('resend-success')
    } catch {
      setState('resend-success')
    } finally {
      setIsResending(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface py-12 px-4 sm:px-6 lg:px-8">
      <div className="bg-surface-container-lowest rounded-xl p-8 w-full max-w-md" style={{ boxShadow: 'var(--shadow-card)' }}>
        <div className="text-center mb-8">
          <h2 className="font-headline font-black text-primary text-3xl tracking-tight">
            Monie
          </h2>
        </div>

        <div className="text-center">
          {state === 'loading' && (
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-on-surface-variant">Verifying your email...</p>
            </div>
          )}

          {state === 'success' && (
            <div className="space-y-4">
              <div className="w-12 h-12 mx-auto bg-green-100 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="font-headline font-bold text-on-surface text-lg">Email Verified!</h3>
              <p className="text-sm text-on-surface-variant">You can now close this page.</p>
              <Link
                to="/"
                className="inline-block px-4 py-2 text-sm font-medium rounded-lg text-on-primary bg-gradient-to-br from-primary to-primary-dim hover:opacity-90 active:scale-[0.98] transition-all"
              >
                Go to Dashboard
              </Link>
            </div>
          )}

          {state === 'error' && (
            <div className="space-y-4">
              <div className="w-12 h-12 mx-auto bg-red-100 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h3 className="font-headline font-bold text-on-surface text-lg">Invalid or Expired Link</h3>
              <p className="text-sm text-on-surface-variant">
                This verification link is invalid or has expired.
              </p>
              <button
                type="button"
                onClick={() => setState('resend')}
                className="text-primary hover:text-primary-dim text-sm font-medium"
              >
                Resend verification email
              </button>
            </div>
          )}

          {state === 'resend' && (
            <form onSubmit={handleResend} className="space-y-4">
              <h3 className="font-headline font-bold text-on-surface text-lg">Resend Verification</h3>
              <p className="text-sm text-on-surface-variant">Enter your email to receive a new verification link.</p>
              <input
                type="email"
                required
                value={resendEmail}
                onChange={(e) => setResendEmail(e.target.value)}
                className="w-full bg-surface-container-highest border-none rounded-lg px-3 py-2 font-mono text-sm text-on-surface focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary-container focus:outline-none transition-all"
                placeholder="Enter your email address"
              />
              <button
                type="submit"
                disabled={isResending}
                className="w-full py-2 px-4 text-sm font-medium rounded-lg text-on-primary bg-gradient-to-br from-primary to-primary-dim hover:opacity-90 active:scale-[0.98] transition-all disabled:opacity-50"
              >
                {isResending ? 'Sending...' : 'Send Verification Email'}
              </button>
            </form>
          )}

          {state === 'resend-success' && (
            <div className="space-y-4">
              <div className="w-12 h-12 mx-auto bg-green-100 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="font-headline font-bold text-on-surface text-lg">Check Your Email</h3>
              <p className="text-sm text-on-surface-variant">
                If your email is unverified, a new verification email has been sent.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
