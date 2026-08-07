import { useState, useEffect } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { EyeIcon, EyeOffIcon, LockIcon, LogoIcon, MailIcon, UserIcon, UserPlusIcon, GoogleIcon } from '@/components/Icons'
import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'
import { loginWithGoogle, signupWithFirebaseEmail, checkGoogleRedirect, firebaseUserToStoreUser, type FirebaseUser } from '@/services/firebase'

const API_BASE = import.meta.env.VITE_API_URL

export default function Register() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const [form, setForm] = useState({ email: '', fullName: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchParams] = useSearchParams()

  // Where a guest was headed when the login-only guard redirected them to
  // /login (which then linked here). Internal paths only.
  const rawRedirect = searchParams.get('redirect')
  const safeRedirect =
    rawRedirect && rawRedirect.startsWith('/') && !rawRedirect.startsWith('//')
      ? rawRedirect
      : null

  /**
   * Exchange a Firebase ID token for the profile. The backend auto-creates
   * the Firestore user on first sign-in, so no separate register step exists.
   * Email signups land on the verification screen (their account isn't
   * verified yet); Google accounts are already verified → back to where the
   * user was headed, or the dashboard.
   */
  const finishAuth = async (idToken: string, user: FirebaseUser, dest = '/dashboard') => {
    // Navigate immediately — never block the spinner on a backend round trip
    // (the free Render instance cold-starts slowly). The Firestore user is
    // auto-created by the backend on the first authenticated call; the
    // authoritative profile is applied in the background when it responds.
    setAuth(idToken, '', firebaseUserToStoreUser(user))
    navigate(dest, { replace: true })
    try {
      const { data: u } = await axios.post(`${API_BASE}/auth/firebase`, { id_token: idToken })
      const state = useAuthStore.getState()
      if (state.accessToken === idToken) {
        state.setUser({
          id: u.id, email: u.email, username: u.username,
          fullName: u.full_name, avatarUrl: u.avatar_url, isSuperuser: u.is_superuser,
        })
      }
    } catch {
      // Optimistic profile stays — backend calls still authenticate via token.
    }
  }

  // On mount: check if we're returning from a Google redirect
  useEffect(() => {
    const cleanup = checkGoogleRedirect(
      async (user, idToken) => {
        // Redirect-return path (popup unavailable): land back on the page
        // the guest was headed to, same as the inline popup path.
        await finishAuth(idToken, user, safeRedirect ?? '/dashboard')
      },
      () => { setGoogleLoading(false) },
    )
    return cleanup
  }, [])

  const handleGoogleLogin = async () => {
    setError('')
    setGoogleLoading(true)
    // Last-resort guard: if the popup/redirect flow hangs (Safari storage
    // blocked, in-app browser, slow cold start), never leave the user stuck
    // on the full-screen spinner — restore the form so they can retry or
    // use email. Cleared once the flow resolves one way or the other.
    let settled = false
    const hangGuard = setTimeout(() => {
      if (!settled) {
        setGoogleLoading(false)
        setError('Google sign-in is taking too long. Please try again, or register with email below.')
      }
    }, 15000)
    try {
      const result = await loginWithGoogle()
      settled = true
      clearTimeout(hangGuard)
      // Popup path: sign-in completed inline → finish auth now.
      // Redirect path (result === null): page navigates away to Google; the
      // mount effect's checkGoogleRedirect finishes auth on return.
      if (result) {
        await finishAuth(result.idToken, result.user, safeRedirect ?? '/dashboard')
        return
      }
      // The redirect was initiated, but the browser can silently swallow the
      // navigation (popup blockers, Safari ITP, in-app browsers). If we're
      // still mounted after a moment, the user never left: restore the form
      // and let them retry — late redirect results are still consumed by
      // checkGoogleRedirect on a subsequent mount.
      setTimeout(() => {
        setGoogleLoading(false)
        setError('Google sign-in didn\u2019t complete in this window. Please try again, or register with email below.')
      }, 6000)
    } catch (err: any) {
      settled = true
      clearTimeout(hangGuard)
      // User closing the popup is not an error — just show the form again.
      if (err?.code === 'auth/popup-closed-by-user' || err?.code === 'auth/user-cancelled') {
        setGoogleLoading(false)
        return
      }
      // Benign SDK storage error fired while the tab is hidden — loginWithGoogle
      // already fell back to redirect for it; don't show a scary banner.
      if (!err?.code && typeof err?.message === 'string' && /Database is (closing|hidden)|database connection is closing/i.test(err.message)) {
        setGoogleLoading(false)
        return
      }
      setError(err.message || 'Google Sign-In failed. Please try again.')
      setGoogleLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      // Create the account in Firebase Auth (email verification is sent).
      const { user, idToken } = await signupWithFirebaseEmail(form.email, form.password)
      // Backend auto-creates the Firestore user from the verified token.
      // Redirect to the verification screen — the session is live, the
      // account just isn't verified yet.
      await finishAuth(idToken, user, '/verify-email')
    } catch (err: any) {
      const code: string = err?.code || ''
      if (code.includes('email-already-in-use')) {
        setError('An account with this email already exists. Try signing in instead.')
      } else if (code.includes('weak-password')) {
        setError('Password is too weak. Use at least 6 characters.')
      } else {
        setError(err?.response?.data?.detail || err?.message || 'Registration failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  if (googleLoading) {
    return (
      <div className="min-h-screen relative flex items-center justify-center">
        <div className="stage" aria-hidden />
        <div className="text-center space-y-4">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-[#16151a] to-[#08080b] border border-primary-600/40 shadow-lg shadow-primary-500/25 mx-auto">
            <LogoIcon size={30} />
          </div>
          <div className="flex items-center gap-3 text-surface-400">
            <div className="w-5 h-5 border-2 border-surface-700 border-t-primary-400 rounded-full animate-spin" />
            <span className="text-sm">Signing you in…</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen relative flex items-center justify-center p-4">
      <div className="stage" aria-hidden />
      <div className="w-full max-w-md relative">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-[#16151a] to-[#08080b] border border-primary-600/40 shadow-lg shadow-primary-500/25 mb-5">
            <LogoIcon size={30} />
          </div>
          <p className="microlabel mb-3">AgentOS Studio | agent orchestration</p>
          <h1 className="text-4xl font-light tracking-tight serif-display text-surface-100">
            Create Account
          </h1>
          <p className="text-surface-400 text-sm mt-2">Join AgentOS Studio</p>
        </div>

        <div className="glass-strong rounded-2xl p-6 space-y-4 shadow-glass">
          {error && (
            <div data-testid="auth-error" className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={handleGoogleLogin}
            disabled={loading}
            className="w-full flex items-center justify-center gap-3 py-2.5 px-4 rounded-xl bg-surface-900/80 hover:bg-surface-800/80 border border-surface-700/50 text-surface-100 font-medium text-sm transition-all shadow-sm hover:shadow-md hover:border-surface-600 disabled:opacity-50"
          >
            <GoogleIcon size={18} />
            <span>Sign up with Google</span>
          </button>

          <div className="flex items-center my-4">
            <div className="flex-grow border-t border-surface-800"></div>
            <span className="px-3 text-xs text-surface-500 uppercase tracking-wider">or register with email</span>
            <div className="flex-grow border-t border-surface-800"></div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Full name</label>
              <div className="relative">
                <UserIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
                <input type="text" placeholder="John Doe" value={form.fullName}
                  onChange={(e) => setForm({ ...form, fullName: e.target.value })}
                  className="input-field pl-10" required />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Email</label>
              <div className="relative">
                <MailIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
                <input type="email" placeholder="you@example.com" value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="input-field pl-10" required />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Password</label>
              <div className="relative">
                <LockIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
                <input type={showPassword ? 'text' : 'password'} placeholder="••••••••" value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="input-field pl-10 pr-10" required minLength={6} />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300">
                  {showPassword ? <EyeOffIcon size={16} /> : <EyeIcon size={16} />}
                </button>
              </div>
            </div>

            <button type="submit" disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 py-2.5">
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <UserPlusIcon size={16} />
              )}
              {loading ? 'Creating account...' : 'Create account'}
            </button>
          </form>

          <p className="text-center text-sm text-surface-400">
            Already have an account?{' '}
            <Link
              to={`/login${safeRedirect ? `?redirect=${encodeURIComponent(safeRedirect)}` : ''}`}
              className="text-primary-400 hover:text-primary-300 font-medium transition-colors"
            >
              Sign in
            </Link>
          </p>

          <p className="text-center text-xs text-surface-600 pt-3 border-t border-surface-800/60">
            By creating an account, you agree to our{' '}
            <Link to="/terms" className="text-surface-500 hover:text-surface-300 transition-colors">Terms</Link>
            {' '}and{' '}
            <Link to="/privacy" className="text-surface-500 hover:text-surface-300 transition-colors">Privacy Policy</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
