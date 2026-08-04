import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { EyeIcon, EyeOffIcon, LockIcon, LogInIcon, LogoIcon, MailIcon, GoogleIcon } from '@/components/Icons'
import { useAuthStore } from '@/stores/authStore'
import { loginWithGoogle, checkGoogleRedirect, loginWithFirebaseEmail, firebaseUserToStoreUser, type FirebaseUser } from '@/services/firebase'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL

function firebaseAuthErrorMessage(err: any): string {
  const code: string = err?.code || ''
  if (code.includes('user-not-found') || code.includes('wrong-password') || code.includes('invalid-credential')) {
    return 'Invalid email or password.'
  }
  if (code.includes('too-many-requests')) return 'Too many attempts. Please try again later.'
  if (code.includes('invalid-email')) return 'Please enter a valid email address.'
  if (code.includes('user-disabled')) return 'This account has been disabled.'
  return err?.message || 'Login failed. Please try again.'
}

export default function Login() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const [form, setForm] = useState({ email: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(true)
  const [error, setError] = useState('')

  // Complete authentication instantly from the Firebase ID token — no waiting
  // on a backend round-trip. The full Firestore profile (id, username,
  // superuser flag) refreshes in the background once it arrives.
  const finishAuth = async (idToken: string, user: FirebaseUser) => {
    setAuth(idToken, '', firebaseUserToStoreUser(user))
    navigate('/dashboard', { replace: true })

    // Background: fetch the full profile from the backend (auto-creates the
    // Firestore user on first sign-in). Apply only if still signed in.
    try {
      const { data: u } = await axios.get(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${idToken}` },
      })
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
      // onSuccess: redirect completed → resolve profile via our backend
      async (user, idToken) => {
        await finishAuth(idToken, user)
      },
      // onNoRedirect: normal page load, just show the form
      () => { setGoogleLoading(false) }
    )
    return cleanup
  }, [])

  const handleGoogleLogin = async () => {
    setError('')
    setGoogleLoading(true)
    try {
      const result = await loginWithGoogle()
      // Popup path: sign-in completed inline → finish auth now.
      // Redirect path (result === null): page navigated away to Google; the
      // mount effect's checkGoogleRedirect finishes auth on return.
      if (result) {
        await finishAuth(result.idToken, result.user)
      }
    } catch (err: any) {
      // User closing the popup is not an error — just show the form again.
      if (err?.code === 'auth/popup-closed-by-user' || err?.code === 'auth/user-cancelled') {
        setGoogleLoading(false)
        return
      }
      // Message-only SDK storage errors ("Database is closing/hidden" fired
      // while the tab is hidden) are benign — loginWithGoogle already falls
      // back to the redirect flow for them; if one escapes, treat it like a
      // cancelled popup and show the form again, not a scary banner.
      if (!err?.code && typeof err?.message === 'string' && /Database is (closing|hidden)|database connection is closing/i.test(err.message)) {
        setGoogleLoading(false)
        return
      }
      setError(err.message || 'Google Sign-In failed.')
      setGoogleLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { user, idToken } = await loginWithFirebaseEmail(form.email, form.password)
      await finishAuth(idToken, user)
    } catch (err: any) {
      setError(firebaseAuthErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  // Show spinner while checking for Google redirect result
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
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-[#16151a] to-[#08080b] border border-primary-600/40 shadow-lg shadow-primary-500/25 mb-5">
            <LogoIcon size={30} />
          </div>
          <p className="microlabel mb-3">AgentOS Studio — agent orchestration</p>
          <h1 className="text-4xl font-light tracking-tight serif-display text-surface-100">
            Welcome back
          </h1>
          <p className="text-surface-400 text-sm mt-2">Sign in to your account</p>
        </div>

        {/* Form */}
        <div className="glass-strong rounded-2xl p-6 space-y-4 shadow-glass">
          {error && (
            <div data-testid="auth-error" className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Google Sign-In — popup-first */}
          <button
            type="button"
            onClick={handleGoogleLogin}
            disabled={loading}
            className="w-full flex items-center justify-center gap-3 py-2.5 px-4 rounded-xl bg-surface-900/80 hover:bg-surface-800/80 border border-surface-700/50 text-surface-100 font-medium text-sm transition-all shadow-sm hover:shadow-md hover:border-surface-600 disabled:opacity-50"
          >
            <GoogleIcon size={18} />
            <span>Sign in with Google</span>
          </button>

          <div className="flex items-center my-4">
            <div className="flex-grow border-t border-surface-800"></div>
            <span className="px-3 text-xs text-surface-500 uppercase tracking-wider">or continue with email</span>
            <div className="flex-grow border-t border-surface-800"></div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Email</label>
              <div className="relative">
                <MailIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
                <input
                  type="email"
                  placeholder="you@example.com"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="input-field pl-10"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Password</label>
              <div className="relative">
                <LockIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="input-field pl-10 pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  title={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300"
                >
                  {showPassword ? <EyeOffIcon size={16} /> : <EyeIcon size={16} />}
                </button>
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
                <LogInIcon size={16} />
              )}
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          <p className="text-center text-sm text-surface-400">
            Don't have an account?{' '}
            <Link to="/register" className="text-primary-400 hover:text-primary-300 font-medium transition-colors">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
