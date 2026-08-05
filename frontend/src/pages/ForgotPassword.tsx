import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeftIcon, CheckCircleIcon, LogoIcon, MailIcon, RefreshCwIcon } from '@/components/Icons'
import { sendPasswordResetEmailWrapper } from '@/services/firebase'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)
  const [error, setError] = useState('')

  const send = async (address: string) => {
    await sendPasswordResetEmailWrapper(address)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await send(email.trim())
      setSubmitted(true)
    } catch (err: any) {
      const code: string = err?.code || ''
      // Anti-enumeration: unknown accounts (auth/user-not-found) show the
      // same success screen as real ones — never reveal which emails exist.
      if (code.includes('user-not-found')) {
        setSubmitted(true)
      } else if (code.includes('invalid-email')) {
        setError('Please enter a valid email address.')
      } else if (code.includes('too-many-requests')) {
        setError('Too many requests. Please wait a minute and try again.')
      } else {
        setError(err?.message || 'Could not send the reset email. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    setError('')
    setResending(true)
    try {
      await send(email.trim())
    } catch (err: any) {
      const code: string = err?.code || ''
      if (code.includes('invalid-email')) {
        setError('Please enter a valid email address.')
      } else if (code.includes('too-many-requests')) {
        setError('Too many requests. Please wait a minute and try again.')
      } else if (!code.includes('user-not-found')) {
        setError(err?.message || 'Could not resend the email. Please try again.')
      }
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="min-h-screen relative flex items-center justify-center p-4">
      <div className="stage" aria-hidden />
      <div className="w-full max-w-md relative">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-[#16151a] to-[#08080b] border border-primary-600/40 shadow-lg shadow-primary-500/25 mb-5">
            <LogoIcon size={30} />
          </div>
          <p className="microlabel mb-3">AgentOS Studio — account recovery</p>
          <h1 className="text-4xl font-light tracking-tight serif-display text-surface-100">
            {submitted ? 'Check your inbox' : 'Reset your password'}
          </h1>
          <p className="text-surface-400 text-sm mt-2">
            {submitted
              ? 'A password reset link is on its way.'
              : 'Enter your email and we\'ll send you a link to set a new password.'}
          </p>
        </div>

        <div className="glass-strong rounded-2xl p-6 space-y-4 shadow-glass">
          {submitted ? (
            <div className="flex flex-col items-center py-4 space-y-4">
              <div className="w-16 h-16 rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
                <CheckCircleIcon size={30} className="text-emerald-400" />
              </div>
              <p className="text-sm text-surface-300 text-center leading-relaxed">
                If an account exists for <span className="font-medium text-surface-100">{email.trim() || 'your email'}</span>,
                a reset link has been sent to it. It expires in about an hour — check your spam folder if you don't see it.
              </p>
              <button
                type="button"
                onClick={handleResend}
                disabled={resending}
                className="btn-primary w-full flex items-center justify-center gap-2 py-2.5"
              >
                <RefreshCwIcon size={15} className={resending ? 'animate-spin' : ''} />
                {resending ? 'Resending…' : 'Resend email'}
              </button>
              <Link
                to="/login"
                className="flex items-center gap-1.5 text-sm text-primary-400 hover:text-primary-300 font-medium transition-colors"
              >
                <ArrowLeftIcon size={14} />
                Back to sign in
              </Link>
            </div>
          ) : (
            <>
              {error && (
                <div className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-1.5">Email</label>
                  <div className="relative">
                    <MailIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
                    <input
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="input-field pl-10"
                      required
                      autoFocus
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary w-full flex items-center justify-center gap-2 py-2.5"
                >
                  {loading ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <MailIcon size={16} />
                  )}
                  {loading ? 'Sending…' : 'Send reset link'}
                </button>
              </form>

              <p className="text-center text-sm text-surface-400">
                Remembered it?{' '}
                <Link to="/login" className="text-primary-400 hover:text-primary-300 font-medium transition-colors">
                  Sign in
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
