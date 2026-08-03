import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { EyeIcon, EyeOffIcon, LockIcon, LogInIcon, LogoIcon, MailIcon, GoogleIcon } from '@/components/Icons'
import { useAuthStore } from '@/stores/authStore'
import { loginWithGoogle, checkGoogleRedirect, loginWithFirebaseEmail } from '@/services/firebase'
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

  // Complete authentication: exchange the Firebase ID token for the profile
  const finishAuth = async (idToken: string, email?: string | null, displayName?: string | null, photoURL?: string | null) => {
    try {
      const { data: u } = await axios.get(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${idToken}` },
      })
      setAuth(idToken, '', {
        id: u.id, email: u.email, username: u.username,
        fullName: u.full_name, avatarUrl: u.avatar_url, isSuperuser: u.is_superuser,
      })
    } catch {
      setAuth(idToken, '', {
        id: '', email: email || '', username: displayName || '',
        fullName: displayName || 'User', avatarUrl: photoURL || undefined,
      })
    }
    navigate('/dashboard', { replace: true })
  }

  // On mount: check if we're returning from a Google redirect
  useEffect(() => {
    const cleanup = checkGoogleRedirect(
      // onSuccess: redirect completed → resolve profile via our backend
      async (user, idToken) => {
        await finishAuth(idToken, user.email, user.displayName, user.photoURL)
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
      await loginWithGoogle()
      // Page navigates away to Google — result handled by checkGoogleRedirect on return
    } catch (err: any) {
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
      await finishAuth(idToken, user.email, user.displayName, user.photoURL)
    } catch (err: any) {
      setError(firebaseAuthErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  // Show spinner while checking for Google redirect result
  if (googleLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-950">
        <div className="text-center space-y-4">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-lg shadow-primary-500/20">
            <LogoIcon size={28} className="text-white" />
          </div>
          <div className="flex items-center gap-3 text-surface-400">
            <div className="w-5 h-5 border-2 border-surface-600 border-t-primary-500 rounded-full animate-spin" />
            <span className="text-sm">Signing you in…</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-950 p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-lg shadow-primary-500/20 mb-4">
            <LogoIcon size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gradient">AgentOS Studio</h1>
          <p className="text-surface-400 text-sm mt-2">Sign in to your account</p>
        </div>

        {/* Form */}
        <div className="glass-panel p-6 space-y-4">
          {error && (
            <div data-testid="auth-error" className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Google Sign-In — same tab redirect, no popup */}
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
