import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { toast } from '@/components/Toast'
import { SkeletonPage } from '@/components/Skeleton'
import { KeyIcon, SaveIcon, EyeIcon, EyeOffIcon, CameraIcon } from '@/components/Icons'
import { uploadAvatar, changeFirebasePassword } from '@/services/firebase'

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

  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: () => api.get<UserProfile>('/users/me').then((r) => r.data),
  })

  useEffect(() => {
    if (profile) {
      setFullName(profile.full_name || '')
      setEmail(profile.email)
      setAvatarUrl(profile.avatar_url || '')
    }
  }, [profile])

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
      return api.patch(`/users/${profile?.id}`, payload)
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

  if (isLoading) return <SkeletonPage />

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-surface-100">Settings</h1>
        <p className="text-surface-400 mt-1">Manage your profile and account settings</p>
      </div>

      {/* Profile Section */}
      <form onSubmit={handleProfileSubmit} className="glass-panel p-6 space-y-6">
        <div className="flex items-center gap-4 pb-4 border-b border-surface-700/30">
          {/* Avatar Picture Picker */}
          <div className="relative group cursor-pointer w-16 h-16 rounded-full overflow-hidden border-2 border-primary-500/40 hover:border-primary-500 transition-all shadow-md flex-shrink-0">
            {avatarUrl ? (
              <img src={avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full bg-surface-800 flex items-center justify-center text-surface-300 font-bold text-lg">
                {fullName ? fullName.charAt(0).toUpperCase() : profile?.username?.charAt(0).toUpperCase()}
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
            <h2 className="text-lg font-semibold text-surface-100">{fullName || profile?.username}</h2>
            <p className="text-xs text-surface-400">Username: @{profile?.username}</p>
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

        {/* Verification status */}
        <div className="flex items-center gap-2 text-xs">
          <span className={profile?.is_verified ? 'text-emerald-400' : 'text-amber-400'}>
            {profile?.is_verified ? '✅ Verified' : '⚠️ Not verified'}
          </span>
          <span className="text-surface-600">|</span>
          <span className="text-surface-500">
            Joined {profile?.created_at ? new Date(profile.created_at).toLocaleDateString() : '—'}
          </span>
          {profile?.last_login_at && (
            <>
              <span className="text-surface-600">|</span>
              <span className="text-surface-500">
                Last login: {new Date(profile.last_login_at).toLocaleDateString()}
              </span>
            </>
          )}
        </div>

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
          <span className="text-surface-300 font-mono text-xs">{profile?.id}</span>
        </div>
      </div>
    </div>
  )
}
