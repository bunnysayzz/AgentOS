import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { toast } from '@/components/Toast'
import { SkeletonPage } from '@/components/Skeleton'
import { KeyIcon, SaveIcon, EyeIcon, EyeOffIcon, CameraIcon, RefreshCwIcon, MailIcon, DownloadIcon, TrashIcon, AlertTriangleIcon } from '@/components/Icons'
import { uploadAvatar, changeFirebasePassword, firebaseAuth, resendVerificationEmail, reloadFirebaseUser, firebaseSignOut, deleteAvatar } from '@/services/firebase'
import { confirm } from '@/components/ConfirmDialog'

interface UserProfile {
  id: string
  email: string
  username: string
  full_name: string | null
  avatar_url: string | null
  is_active: boolean
  is_superuser: boolean
  is_verified: boolean
  last_login_at: string | null
  created_at: string
  updated_at: string | null
}

export default function Profile() {
  const qc = useQueryClient()
  const setUser = useAuthStore((s) => s.setUser)
  // Optimistic identity from the auth store (set at login from Firebase
  // claims — includes the Google photo/name). Used as an immediate fallback
  // while /users/me loads, and when it errors.
  const storeUser = useAuthStore((s) => s.user)

  // Profile form
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [avatarUrl, setAvatarUrl] = useState('')
  const [avatarUploading, setAvatarUploading] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  // Note: email is intentionally NOT editable here. It's owned by Firebase
  // Auth (single source of truth) — changing the Firestore doc without the
  // ID token would desync them and auto-create a duplicate account on login.

  // Password form
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  // Live email-verification state (Firebase is the source of truth; the
  // backend snapshot refreshes on next login).
  const [liveVerified, setLiveVerified] = useState<boolean | null>(null)
  const [verifyBusy, setVerifyBusy] = useState(false)
  const [verifyMessage, setVerifyMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  const { data: profile, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['profile'],
    queryFn: () => api.get<UserProfile>('/users/me').then((r) => r.data),
    retry: 1,
  })

  // Fallback profile assembled from the auth store (kept in sync on login
  // and after profile saves), so the page is never blank even if the API
  // temporarily fails.
  const fallbackProfile: UserProfile | undefined = profile ?? (storeUser
    ? {
        id: storeUser.id,
        email: storeUser.email,
        username: storeUser.username,
        full_name: storeUser.fullName || null,
        avatar_url: storeUser.avatarUrl || null,
        is_active: true,
        is_superuser: !!storeUser.isSuperuser,
        is_verified: true,
        last_login_at: null,
        created_at: '',
        updated_at: null,
      }
    : undefined)
  const display = fallbackProfile

  // Live verification status: prefer Firebase's real-time state (kept fresh
  // by the Refresh button), fall back to the backend snapshot.
  useEffect(() => {
    const u = firebaseAuth?.currentUser
    setLiveVerified(u ? u.emailVerified : null)
  }, [])
  const isVerified = liveVerified ?? (firebaseAuth?.currentUser ? firebaseAuth.currentUser.emailVerified : undefined) ?? display?.is_verified

  useEffect(() => {
    if (display) {
      setFullName(display.full_name || '')
      setEmail(display.email)
      setAvatarUrl(display.avatar_url || '')
    }
  }, [display?.id, display?.full_name, display?.email, display?.avatar_url])

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 5 * 1024 * 1024) {
      toast.error('File too large', 'Please select an image smaller than 5MB.')
      return
    }
    // Preview locally first, upload to Firebase Storage on save
    const reader = new FileReader()
    reader.onloadend = () => {
      if (typeof reader.result === 'string') {
        setAvatarUrl(reader.result)
        setSelectedFile(file)
        toast.success('Image selected', 'Click Save Changes to upload your new profile picture.')
      }
    }
    reader.readAsDataURL(file)
  }

  // Update profile
  const updateMutation = useMutation({
    mutationFn: async (data: { full_name?: string; email?: string; avatar_url?: string }) => {
      // If a new avatar was picked, upload it to Firebase Storage first and
      // persist the resulting download URL (not a base64 blob).
      let payload = data
      if (selectedFile) {
        setAvatarUploading(true)
        try {
          const url = await uploadAvatar(selectedFile)
          payload = { ...data, avatar_url: url }
        } finally {
          setAvatarUploading(false)
        }
      }
      return api.patch(`/users/${display?.id}`, payload)
    },
    onSuccess: (res) => {
      const u = res.data
      setSelectedFile(null)
      setUser({ id: u.id, email: u.email, username: u.username, fullName: u.full_name, avatarUrl: u.avatar_url })
      toast.success('Profile updated', 'Your profile has been saved.')
      qc.invalidateQueries({ queryKey: ['profile'] })
    },
    onError: (err: any) => {
      toast.error('Update failed', err?.response?.data?.detail || err?.message || 'Could not update profile')
    },
  })

  // Change password — handled by Firebase Auth, not the backend
  const passwordMutation = useMutation({
    mutationFn: (data: { current_password: string; new_password: string }) =>
      changeFirebasePassword(data.current_password, data.new_password),
    onSuccess: () => {
      toast.success('Password changed', 'Your password has been updated. Use it next time you sign in.')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    },
    onError: (err: any) => {
      const code: string = err?.code || ''
      if (code.includes('wrong-password') || code.includes('invalid-credential')) {
        toast.error('Password change failed', 'Current password is incorrect.')
      } else if (code.includes('weak-password')) {
        toast.error('Password change failed', 'New password is too weak. Use at least 6 characters.')
      } else {
        toast.error('Password change failed', err?.message || 'Could not change password')
      }
    },
  })

  const handleProfileSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateMutation.mutate({
      full_name: fullName || undefined,
      email: email !== profile?.email ? email : undefined,
      avatar_url: avatarUrl || undefined,
    })
  }

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (newPassword !== confirmPassword) {
      toast.error('Passwords do not match', 'Please make sure both passwords match.')
      return
    }
    if (newPassword.length < 6) {
      toast.error('Password too short', 'Password must be at least 6 characters.')
      return
    }
    passwordMutation.mutate({ current_password: currentPassword, new_password: newPassword })
  }

  // Email verification actions (Firebase owns verification, not the backend)
  const handleResendVerification = async () => {
    setVerifyMessage(null)
    setVerifyBusy(true)
    try {
      await resendVerificationEmail()
      setVerifyMessage({ kind: 'success', text: 'Verification email sent — check your inbox (and spam).' })
    } catch (err: any) {
      setVerifyMessage({ kind: 'error', text: err?.message || 'Could not send the verification email.' })
    } finally {
      setVerifyBusy(false)
    }
  }

  const handleRefreshVerification = async () => {
    setVerifyMessage(null)
    setVerifyBusy(true)
    try {
      const u = await reloadFirebaseUser()
      if (u) setLiveVerified(u.emailVerified)
      setVerifyMessage({ kind: 'success', text: 'Verification status refreshed.' })
      qc.invalidateQueries({ queryKey: ['profile'] })
    } catch {
      setVerifyMessage({ kind: 'error', text: 'Could not refresh verification status.' })
    } finally {
      setVerifyBusy(false)
    }
  }

  // Danger Zone — export / delete (GDPR)
  const [exporting, setExporting] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const handleExportData = async () => {
    setExporting(true)
    try {
      const res = await api.get('/users/me/export', { responseType: 'blob' })
      const blob = new Blob([res.data], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `agentos-export-${display?.id ?? 'me'}.json`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      toast.success('Export ready', 'Your data has been downloaded.')
    } catch (err: any) {
      toast.error('Export failed', err?.response?.data?.detail || err?.message || 'Could not export your data.')
    } finally {
      setExporting(false)
    }
  }

  const handleDeleteAccount = () => {
    confirm.danger(
      'Delete your account?',
      'This permanently deletes your profile, the workspaces you own, and everything in them. This cannot be undone.',
      async () => {
        setDeleting(true)
        try {
          await api.delete('/users/me')
          // Best-effort cleanup of the avatar file in Firebase Storage.
          await deleteAvatar()
          toast.success('Account deleted', 'Your account and data have been permanently removed.')
          // Sign out of Firebase + clear local state, then land on the login page.
          await firebaseSignOut(firebaseAuth)
          window.location.href = '/login'
        } catch (err: any) {
          setDeleting(false)
          toast.error('Delete failed', err?.response?.data?.detail || err?.message || 'Could not delete your account.')
        }
      },
    )
  }

  if (isLoading && !storeUser) return <SkeletonPage />

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div>
          <p className="microlabel mb-1">account</p>
          <h1 className="text-3xl font-light tracking-tight serif-display text-surface-100">Settings</h1>
          <p className="text-surface-400 mt-1.5 text-sm">Manage your profile and account settings</p>
        </div>
      </div>

      {/* Profile fetch error — still usable via the optimistic fallback */}
      {isError && (
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 rounded-xl bg-amber-500/10 border border-amber-500/25 text-amber-300 text-sm">
          <span className="flex-1 min-w-0">
            Couldn't refresh your profile from the server. Showing your saved info — changes you make here will still be applied.
          </span>
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="px-3 py-1.5 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-200 text-xs font-semibold transition-colors disabled:opacity-50 flex items-center gap-1.5"
          >
            <RefreshCwIcon size={12} />
            {isFetching ? 'Retrying…' : 'Retry'}
          </button>
        </div>
      )}

      {/* Profile Section */}
      <form onSubmit={handleProfileSubmit} className="glass-panel p-6 space-y-6">
        <div className="flex items-center gap-4 pb-4 border-b border-surface-700/30">
          {/* Avatar Picture Picker */}
          <div className="relative group cursor-pointer w-16 h-16 rounded-full overflow-hidden border-2 border-primary-500/40 hover:border-primary-500 transition-all shadow-md flex-shrink-0">
            {avatarUrl ? (
              <img src={avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full bg-surface-800 flex items-center justify-center text-surface-300 font-bold text-lg">
                {fullName ? fullName.charAt(0).toUpperCase() : display?.username?.charAt(0).toUpperCase() || 'U'}
              </div>
            )}
            <label className="absolute inset-0 bg-surface-950/75 opacity-0 group-hover:opacity-100 flex flex-col items-center justify-center text-white text-[10px] font-medium transition-all cursor-pointer">
              <CameraIcon size={16} className="mb-0.5" />
              <span>Change</span>
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleImageUpload}
              />
            </label>
          </div>

          <div>
            <h2 className="text-lg font-semibold text-surface-100">{fullName || display?.username || 'User'}</h2>
            <p className="text-xs text-surface-400">Username: @{display?.username || 'user'}</p>
            <label className="inline-flex items-center gap-1 mt-1 text-xs text-primary-400 hover:text-primary-300 font-medium cursor-pointer">
              <CameraIcon size={12} />
              <span>{avatarUploading ? 'Uploading…' : 'Upload new picture'}</span>
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleImageUpload}
              />
            </label>
          </div>
        </div>

        {/* Full Name */}
        <div>
          <label className="block text-sm font-medium text-surface-300 mb-1.5">Full Name</label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Your full name"
            className="input-field"
          />
        </div>

        {/* Email — managed by Firebase Auth; not editable here to keep the
            Firestore doc in sync with the ID token (prevents duplicate accounts) */}
        <div>
          <label className="block text-sm font-medium text-surface-300 mb-1.5">Email</label>
          <input
            type="email"
            value={email}
            readOnly
            disabled
            placeholder="email@example.com"
            className="input-field opacity-70 cursor-not-allowed"
          />
          <p className="text-xs text-surface-500 mt-1">
            Your email is managed by your Firebase account. To change it, update it in Google/Firebase and sign in again.
          </p>
        </div>

        {/* Verification status — live from Firebase when available */}
        <div className="flex items-center gap-2 text-xs">
          <span className={isVerified ? 'text-emerald-400' : 'text-amber-400'}>
            {isVerified ? '✅ Verified' : '⚠️ Not verified'}
          </span>
          <span className="text-surface-600">|</span>
          <span className="text-surface-500">
            Joined {display?.created_at ? new Date(display.created_at).toLocaleDateString() : '—'}
          </span>
          {display?.last_login_at && (
            <>
              <span className="text-surface-600">|</span>
              <span className="text-surface-500">
                Last login: {new Date(display.last_login_at).toLocaleDateString()}
              </span>
            </>
          )}
        </div>

        {!isVerified && (
          <div className="rounded-xl border border-amber-500/25 bg-amber-500/10 p-4 space-y-3">
            <div className="flex items-start gap-2.5">
              <MailIcon size={16} className="text-amber-400 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-amber-200">
                <p className="font-medium text-amber-100">Your email isn't verified yet</p>
                <p className="text-amber-200/80 mt-0.5">
                  Verify it to secure your account and confirm it belongs to you.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleResendVerification}
                disabled={verifyBusy}
                className="px-3 py-1.5 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-200 text-xs font-semibold transition-colors disabled:opacity-50 flex items-center gap-1.5"
              >
                <MailIcon size={12} />
                {verifyBusy ? 'Sending…' : 'Resend verification email'}
              </button>
              <button
                type="button"
                onClick={handleRefreshVerification}
                disabled={verifyBusy}
                className="px-3 py-1.5 rounded-lg bg-surface-900/60 hover:bg-surface-800/70 border border-surface-700/40 text-surface-300 text-xs font-semibold transition-colors disabled:opacity-50 flex items-center gap-1.5"
              >
                <RefreshCwIcon size={12} className={verifyBusy ? 'animate-spin' : ''} />
                Refresh status
              </button>
            </div>
            {verifyMessage && (
              <p className={`text-xs ${verifyMessage.kind === 'success' ? 'text-emerald-300' : 'text-red-400'}`}>
                {verifyMessage.text}
              </p>
            )}
          </div>
        )}

        <div className="pt-2">
          <button
            type="submit"
            disabled={updateMutation.isPending || avatarUploading}
            className="btn-primary flex items-center gap-2"
          >
            <SaveIcon size={16} />
            {updateMutation.isPending || avatarUploading ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>

      {/* Password Section */}
      <form onSubmit={handlePasswordSubmit} className="glass-panel p-6 space-y-5">
        <div className="flex items-center gap-3 pb-4 border-b border-surface-700/30">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
            <KeyIcon size={20} className="text-amber-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-surface-100">Password</h2>
            <p className="text-xs text-surface-500">Update your account password (managed by Firebase)</p>
          </div>
        </div>

        {/* Current Password */}
        <div>
          <label className="block text-sm font-medium text-surface-300 mb-1.5">Current Password</label>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Enter current password"
              className="input-field pr-10"
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300"
            >
              {showPassword ? <EyeOffIcon size={16} /> : <EyeIcon size={16} />}
            </button>
          </div>
        </div>

        {/* New Password */}
        <div>
          <label className="block text-sm font-medium text-surface-300 mb-1.5">New Password</label>
          <div className="relative">
            <input
              type={showNewPassword ? 'text' : 'password'}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="At least 6 characters"
              className="input-field pr-10"
              required
              minLength={6}
            />
            <button
              type="button"
              onClick={() => setShowNewPassword(!showNewPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300"
            >
              {showNewPassword ? <EyeOffIcon size={16} /> : <EyeIcon size={16} />}
            </button>
          </div>
        </div>

        {/* Confirm Password */}
        <div>
          <label className="block text-sm font-medium text-surface-300 mb-1.5">Confirm New Password</label>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Re-enter new password"
            className="input-field"
            required
          />
          {confirmPassword && newPassword !== confirmPassword && (
            <p className="text-xs text-red-400 mt-1">Passwords do not match</p>
          )}
        </div>

        <div className="pt-2">
          <button
            type="submit"
            disabled={passwordMutation.isPending || !currentPassword || !newPassword || !confirmPassword}
            className="btn-primary flex items-center gap-2"
          >
            <KeyIcon size={16} />
            {passwordMutation.isPending ? 'Changing...' : 'Change Password'}
          </button>
        </div>
      </form>

      {/* Account Info */}
      <div className="glass-panel p-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-surface-500">Account ID</span>
          <span className="text-surface-300 font-mono text-xs">{display?.id}</span>
        </div>
      </div>

      {/* Danger Zone — GDPR: export your data or delete your account */}
      <div className="glass-panel p-6 space-y-5 border-red-500/20">
        <div className="flex items-center gap-3 pb-4 border-b border-surface-700/30">
          <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
            <AlertTriangleIcon size={20} className="text-red-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-surface-100">Danger Zone</h2>
            <p className="text-xs text-surface-500">Data portability & account deletion (GDPR/CCPA)</p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl bg-surface-900/50 border border-surface-800 p-4">
          <div>
            <p className="text-sm font-medium text-surface-200">Export your data</p>
            <p className="text-xs text-surface-500 mt-0.5">
              Download a JSON snapshot of your workspaces, agents, workflows, prompts, secrets, and more.
            </p>
          </div>
          <button
            onClick={handleExportData}
            disabled={exporting}
            className="btn-secondary flex items-center gap-2 text-xs px-4 py-2 flex-shrink-0"
          >
            <DownloadIcon size={14} />
            {exporting ? 'Preparing…' : 'Export data'}
          </button>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl bg-red-500/5 border border-red-500/20 p-4">
          <div>
            <p className="text-sm font-medium text-red-300">Delete account</p>
            <p className="text-xs text-surface-500 mt-0.5">
              Permanently deletes your profile, workspaces you own, and everything in them. This cannot be undone.
            </p>
          </div>
          <button
            onClick={handleDeleteAccount}
            disabled={deleting}
            className="px-4 py-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 hover:text-red-300 text-xs font-semibold transition-colors flex items-center gap-2 flex-shrink-0 disabled:opacity-50"
          >
            <TrashIcon size={14} />
            {deleting ? 'Deleting…' : 'Delete account'}
          </button>
        </div>
      </div>
    </div>
  )
}
