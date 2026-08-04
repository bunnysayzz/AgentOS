import { beforeEach, describe, expect, it, vi } from 'vitest'

// setup.ts mocks '@/services/firebase' for other test files — re-enable the
// REAL module here so we exercise the actual sign-in fallback logic.
vi.unmock('@/services/firebase')

// Guarantee the module sees Firebase as configured regardless of whether a
// local .env file is present (CI runs without secrets).
vi.hoisted(() => {
  for (const key of [
    'VITE_FIREBASE_API_KEY',
    'VITE_FIREBASE_AUTH_DOMAIN',
    'VITE_FIREBASE_PROJECT_ID',
    'VITE_FIREBASE_STORAGE_BUCKET',
    'VITE_FIREBASE_MESSAGING_SENDER_ID',
    'VITE_FIREBASE_APP_ID',
  ]) {
    vi.stubEnv(key, 'test-value')
  }
})

const mocks = vi.hoisted(() => {
  const signInWithPopup = vi.fn()
  const signInWithRedirect = vi.fn()
  const getRedirectResult = vi.fn()
  const onAuthStateChanged = vi.fn()
  const signInWithEmailAndPassword = vi.fn()
  const createUserWithEmailAndPassword = vi.fn()
  const sendEmailVerification = vi.fn()
  const signOut = vi.fn()
  const reauthenticateWithCredential = vi.fn()
  const updatePassword = vi.fn()
  class EmailAuthProvider {
    static credential() {
      return {}
    }
  }
  class GoogleAuthProvider {
    setCustomParameters() {
      return this
    }
  }
  const getAuth = vi.fn(() => ({ currentUser: null }))
  const getApps = vi.fn(() => [])
  const getApp = vi.fn(() => ({}))
  const initializeApp = vi.fn(() => ({}))
  const getStorage = vi.fn()
  const ref = vi.fn()
  const uploadBytes = vi.fn()
  const getDownloadURL = vi.fn()
  return {
    signInWithPopup,
    signInWithRedirect,
    getRedirectResult,
    onAuthStateChanged,
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    sendEmailVerification,
    signOut,
    reauthenticateWithCredential,
    updatePassword,
    EmailAuthProvider,
    GoogleAuthProvider,
    getAuth,
    getApps,
    getApp,
    initializeApp,
    getStorage,
    ref,
    uploadBytes,
    getDownloadURL,
  }
})

vi.mock('firebase/auth', () => ({
  getAuth: mocks.getAuth,
  GoogleAuthProvider: mocks.GoogleAuthProvider,
  signInWithPopup: mocks.signInWithPopup,
  signInWithRedirect: mocks.signInWithRedirect,
  getRedirectResult: mocks.getRedirectResult,
  onAuthStateChanged: mocks.onAuthStateChanged,
  signInWithEmailAndPassword: mocks.signInWithEmailAndPassword,
  createUserWithEmailAndPassword: mocks.createUserWithEmailAndPassword,
  sendEmailVerification: mocks.sendEmailVerification,
  signOut: mocks.signOut,
  reauthenticateWithCredential: mocks.reauthenticateWithCredential,
  updatePassword: mocks.updatePassword,
  EmailAuthProvider: mocks.EmailAuthProvider,
}))

vi.mock('firebase/app', () => ({
  initializeApp: mocks.initializeApp,
  getApps: mocks.getApps,
  getApp: mocks.getApp,
}))

vi.mock('firebase/storage', () => ({
  getStorage: mocks.getStorage,
  ref: mocks.ref,
  uploadBytes: mocks.uploadBytes,
  getDownloadURL: mocks.getDownloadURL,
}))

import { loginWithGoogle } from '@/services/firebase'

describe('loginWithGoogle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  it('returns { user, idToken } when the popup completes inline', async () => {
    const user = { uid: 'u1', getIdToken: vi.fn().mockResolvedValue('token-123') }
    mocks.signInWithPopup.mockResolvedValue({ user })

    const result = await loginWithGoogle()

    expect(result).toEqual({ user, idToken: 'token-123' })
    expect(mocks.signInWithRedirect).not.toHaveBeenCalled()
    expect(sessionStorage.getItem('agentos_google_redirect')).toBeNull()
  })

  it('falls back to the same-tab redirect when the popup throws the benign hidden-tab storage error', async () => {
    // Desktop Safari fullscreen: the popup hides the opener tab, and the
    // Firebase SDK's IndexedDB layer throws this message-only error (no code)
    // during sign-in. loginWithGoogle must NOT surface it — it must start the
    // redirect flow instead.
    mocks.signInWithPopup.mockRejectedValue(new Error('Database is closing/hidden'))

    const result = await loginWithGoogle()

    expect(result).toBeNull()
    expect(mocks.signInWithRedirect).toHaveBeenCalledTimes(1)
    expect(sessionStorage.getItem('agentos_google_redirect')).toBe('1')
  })

  it('falls back to the same-tab redirect when the popup is blocked', async () => {
    mocks.signInWithPopup.mockRejectedValue({ code: 'auth/popup-blocked', message: 'Popup blocked' })

    const result = await loginWithGoogle()

    expect(result).toBeNull()
    expect(mocks.signInWithRedirect).toHaveBeenCalledTimes(1)
  })

  it('rethrows the original benign error if starting the redirect also fails', async () => {
    // The popup throws the hidden-tab error AND the redirect fallback fails
    // (e.g. the browser is still mid-flight with the just-opened popup). The
    // benign root cause must win so the UI shows the form again instead of a
    // confusing redirect banner.
    mocks.signInWithPopup.mockRejectedValue(new Error('Database is closing/hidden'))
    mocks.signInWithRedirect.mockRejectedValue({ code: 'auth/cancelled-popup-request', message: 'Popup cancelled' })

    await expect(loginWithGoogle()).rejects.toThrow('Database is closing/hidden')
  })

  it('rethrows real user-facing errors (e.g. wrong account credential)', async () => {
    const realError = { code: 'auth/account-exists-with-different-credential', message: 'This account already exists.' }
    mocks.signInWithPopup.mockRejectedValue(realError)

    await expect(loginWithGoogle()).rejects.toBe(realError)
    expect(mocks.signInWithRedirect).not.toHaveBeenCalled()
  })
})
