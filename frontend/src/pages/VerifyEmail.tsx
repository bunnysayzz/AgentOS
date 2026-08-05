import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CheckCircleIcon, LogoIcon, MailIcon, RefreshCwIcon, AlertCircleIcon, ArrowRightIcon } from '@/components/Icons'
import { firebaseAuth, resendVerificationEmail, reloadFirebaseUser } from '@/services/firebase'
import { useAuthStore } from '@/stores/authStore'

const POLL_INTERVAL_MS = 3000
const SUCCESS_PAUSE_MS = 1400

export default function VerifyEmail() {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const [email, setEmail] = useState('')
  const [verified, setVerified] = useState(false)
  const [sending, setSending] = useState(false)
  const [resendSent, setResendSent] = useState(false)
  const [error, setError] = useState('')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Resolve the initial state, then poll Firebase until the link is clicked
  // (the click lands the user back in any tab — we detect it within seconds,
  // no manual refresh needed). All timers are tracked and cleared on unmount.
  useEffect(() => {
    let successTimer: ReturnType<typeof setTimeout> | null = null

    const clearTimers = () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      if (successTimer) {
        clearTimeout(successTimer)
        successTimer = null
      }
    }

    const startPolling = () => {
      pollRef.current = setInterval(async () => {
        // Don't hammer Firebase Auth from hidden tabs (background + other
        // open tabs) — the user can only click the link while looking at it.
        if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
        try {
          const u = await reloadFirebaseUser()
          if (u?.emailVerified) {
            setVerified(true)
            clearTimers()
            // Brief success pause, then land on the dashboard.
            successTimer = setTimeout(() => navigate('/dashboard', { replace: true }), SUCCESS_PAUSE_MS)
          }
        } catch {
          // Transient (offline, hidden tab) — keep polling on the next tick.
        }
      }, POLL_INTERVAL_MS)
    }

    const resolveSession = () => {
      const user = firebaseAuth?.currentUser
      if (!user) {
        // No Firebase session. If a backend session still exists (e.g. the
        // account was deleted in Firebase), fall through to the dashboard;
        // otherwise ask the user to sign in.
        navigate(isAuthenticated ? '/dashboard' : '/login', { replace: true })
        return
      }
      setEmail(user.email || '')
      if (user.emailVerified) {
        navigate('/dashboard', { replace: true })
        return
      }
      startPolling()
    }

    if (firebaseAuth?.currentUser) {
      resolveSession()
    } else {
      // On a direct page load the persisted session can restore asynchronously
      // — wait a short grace period before bouncing the user to /login.
      successTimer = setTimeout(resolveSession, 600)
    }

    return clearTimers
    // Run once on mount only — the redirect decision + poll loop live in the
    // closure; re-running on identity changes would restart the poll timer.
  }, [])

  const handleResend = async () => {
    setError('')
    setSending(true)
    setResendSent(false)
    try {
      await resendVerificationEmail()
      setResendSent(true)
    } catch (err: any) {
      const code: string = err?.code || ''
      if (code.includes('too-many-requests')) {
        setError('Too many requests. Please wait a minute before resending.')
      } else {
        setError(err?.message || 'Could not send the verification email. Please try again.')
      }
    } finally {
      setSending(false)
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
          <p className="microlabel mb-3">AgentOS Studio — one last step</p>
          <h1 className="text-4xl font-light tracking-tight serif-display text-surface-100">
            {verified ? 'Email verified!' : 'Verify your email'}
          </h1>
          <p className="text-surface-400 text-sm mt-2">
            {verified
              ? 'Your account is ready. Taking you to your dashboard…'
              : 'We sent a verification link to your inbox.'}
          </p>
        </div>

        <div className="glass-strong rounded-2xl p-6 space-y-5 shadow-glass">
          {verified ? (
            <div className="flex flex-col items-center py-4 space-y-3">
              <div className="w-16 h-16 rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
                <CheckCircleIcon size={30} className="text-emerald-400" />
              </div>
              <p className="text-surface-300 text-sm text-center">
                {email ? (
                  <>
                    <span className="font-medium text-surface-100">{email}</span> is now verified.
                  </>
                ) : (
                  'Your email is now verified.'
                )}
              </p>
            </div>
          ) : (
            <>
              {/* The address the link was sent to */}
              <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-surface-900/60 border border-surface-700/40">
                <div className="w-9 h-9 rounded-lg bg-primary-500/10 border border-primary-500/20 flex items-center justify-center flex-shrink-0">
                  <MailIcon size={17} className="text-primary-400" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-surface-500">Verification link sent to</p>
                  <p className="text-sm font-medium text-surface-100 truncate">{email || 'your email address'}</p>
                </div>
              </div>

              {/* Live status */}
              <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
                <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-60" />
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-400" />
                </span>
                <p className="text-sm text-amber-200">
                  Waiting for verification — open the link in the email and this page updates automatically.
                </p>
              </div>

              {resendSent && (
                <div data-testid="resend-confirmation" className="px-4 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm">
                  Verification email sent again. Check your inbox (and spam folder).
                </div>
              )}
              {error && (
                <div className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  {error}
                </div>
              )}

              <div className="flex flex-col gap-2.5 pt-1">
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={sending}
                  className="btn-primary w-full flex items-center justify-center gap-2 py-2.5"
                >
                  <RefreshCwIcon size={15} className={sending ? 'animate-spin' : ''} />
                  {sending ? 'Sending…' : 'Resend verification email'}
                </button>
                <p className="text-center text-sm text-surface-400">
                  Didn't get it? Check your spam folder, or{' '}
                  <button
                    type="button"
                    onClick={handleResend}
                    disabled={sending}
                    className="text-primary-400 hover:text-primary-300 font-medium transition-colors"
                  >
                    send it again
                  </button>
                </p>
              </div>
            </>
          )}

          <div className="pt-2 border-t border-surface-800">
            <Link
              to="/dashboard"
              className="w-full flex items-center justify-center gap-1.5 text-sm text-surface-400 hover:text-surface-200 transition-colors"
            >
              Continue to dashboard
              <ArrowRightIcon size={14} />
            </Link>
          </div>
        </div>

        <div className="flex items-center justify-center gap-1.5 mt-5 text-xs text-surface-500">
          <AlertCircleIcon size={12} />
          <span>
            Want to use a different email?{' '}
            <Link to="/profile" className="text-primary-400 hover:text-primary-300 transition-colors">
              Manage your account
            </Link>
          </span>
        </div>
      </div>
    </div>
  )
}
