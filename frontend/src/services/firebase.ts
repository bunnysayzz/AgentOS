import { initializeApp, getApps, getApp } from 'firebase/app'
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendEmailVerification,
  signOut,
  User as FirebaseUser,
} from 'firebase/auth'
import { getStorage, ref, uploadBytes, getDownloadURL } from 'firebase/storage'
import {
  reauthenticateWithCredential,
  EmailAuthProvider,
  updatePassword,
} from 'firebase/auth'

const firebaseConfig = {
  apiKey:            import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain:        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId:         import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket:     import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId:             import.meta.env.VITE_FIREBASE_APP_ID,
}

const requiredKeys = ['apiKey', 'authDomain', 'projectId', 'storageBucket', 'messagingSenderId', 'appId'] as const

/**
 * Firebase is the identity provider AND data layer for AgentOS Studio.
 * When the VITE_FIREBASE_* env vars aren't present (CI builds), the module
 * loads safely and every Firebase-dependent action raises a clear error
 * instead of crashing the whole SPA at module load.
 */
export const isFirebaseConfigured = requiredKeys.every((key) => Boolean(firebaseConfig[key]))

const missingKeys = requiredKeys.filter((key) => !firebaseConfig[key])
if (!isFirebaseConfigured && missingKeys.length > 0) {
  console.warn(
    `[Firebase] Not configured — missing ${missingKeys.join(', ')}. ` +
    'Google Sign-In and Firebase-verified signup are disabled; ' +
    'email/password auth continues to work via the backend API.',
  )
}

let app: ReturnType<typeof getApp> | null = null
let auth: ReturnType<typeof getAuth> | null = null
let googleProvider: GoogleAuthProvider | null = null

if (isFirebaseConfigured) {
  app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp()
  auth = getAuth(app)
  googleProvider = new GoogleAuthProvider()
  googleProvider.setCustomParameters({ prompt: 'select_account' })
}

export const firebaseAuth = auth

function notConfiguredError(what: string): Error {
  return new Error(
    `${what} is not configured. Set the VITE_FIREBASE_* environment variables and redeploy to enable it.`,
  )
}

// ─── Session flag ────────────────────────────────────────────────────
// Set only when Google sign-in falls back to the same-tab redirect flow
// (popups unavailable). checkGoogleRedirect() reads it on the return trip to
// distinguish "returning from a Google redirect" from a normal page load.
const REDIRECT_FLAG = 'agentos_google_redirect'

/**
 * Google Sign-In.
 *
 * Primary: signInWithPopup — completes inline, no redirect round-trip. This
 * is far more reliable in production; the previous redirect-only flow could
 * silently fail to complete on the return trip (slow cold starts, ITP,
 * in-app browsers) leaving users stuck on the guest dashboard.
 *
 * Fallback: signInWithRedirect — used only when popups are unavailable
 * (blocked popups, in-app browsers). The page navigates away to Google; on
 * return, checkGoogleRedirect() completes the sign-in.
 *
 * @returns { user, idToken } when the sign-in completed inline (popup path),
 *          or null when the redirect fallback navigated away.
 */
export async function loginWithGoogle(): Promise<{ user: FirebaseUser; idToken: string } | null> {
  if (!auth || !googleProvider) {
    throw notConfiguredError('Google Sign-In')
  }
  try {
    const result = await signInWithPopup(auth, googleProvider)
    const idToken = await result.user.getIdToken()
    return { user: result.user, idToken }
  } catch (err: unknown) {
    const code: string = (err as { code?: string })?.code || ''
    const popupUnavailable = [
      'auth/popup-blocked',
      'auth/operation-not-supported-in-this-environment',
      'auth/cancelled-popup-request',
    ]
    if (popupUnavailable.includes(code)) {
      // Popup not possible → same-tab redirect. checkGoogleRedirect()
      // completes the sign-in when the user returns.
      sessionStorage.setItem(REDIRECT_FLAG, '1')
      await signInWithRedirect(auth, googleProvider)
      return null
    }
    throw err
  }
}

/**
 * Check if we're returning from a Google redirect (the popup fallback path).
 * Call this on login/register page mount.
 *
 * Strategy:
 * 1. No redirect flag → normal page load. Show the form. (Never signs out a
 *    live session — that previously destroyed logged-in users' sessions.)
 * 2. Flag set → try getRedirectResult() first (works in Chrome/Firefox).
 * 3. If getRedirectResult() returns null (Safari ITP) → fall back to
 *    onAuthStateChanged.
 * 4. Clear the flag after processing.
 *
 * @returns an unsubscribe/cleanup function for the effect.
 */
export function checkGoogleRedirect(
  onSuccess: (user: FirebaseUser, idToken: string) => void,
  onNoRedirect: () => void,
): () => void {
  // Firebase not configured → Google auth isn't possible; just show the form.
  if (!auth) {
    onNoRedirect()
    return () => {}
  }
  // Capture a const so TypeScript keeps the narrowing inside the closures
  // below (a module-level `let` is not narrowed inside callbacks).
  const authRef = auth

  // No flag = normal page load, not a redirect return
  if (!sessionStorage.getItem(REDIRECT_FLAG)) {
    onNoRedirect()
    return () => {}
  }

  // Flag is set — we ARE returning from a Google redirect
  sessionStorage.removeItem(REDIRECT_FLAG)

  let handled = false

  // Try getRedirectResult first (works in Chrome/Firefox/Edge)
  getRedirectResult(authRef)
    .then(async (result) => {
      if (handled) return
      if (result) {
        handled = true
        const idToken = await result.user.getIdToken()
        onSuccess(result.user, idToken)
      }
      // If result is null, Safari ITP blocked it — fall through to onAuthStateChanged below
    })
    .catch(() => {
      // getRedirectResult error (Safari ITP) — fall through to onAuthStateChanged
    })

  // Fallback: onAuthStateChanged (catches Safari ITP case)
  const unsubscribe = onAuthStateChanged(authRef, async (user) => {
    if (handled) return
    if (user) {
      handled = true
      unsubscribe()
      const idToken = await user.getIdToken()
      onSuccess(user, idToken)
    }
  })

  // Slow connections / cold starts can exceed a few seconds. If nothing has
  // completed after 20s, show the form — but KEEP the listener alive so the
  // sign-in result is still consumed if it lands later (no lost logins).
  const timeout = setTimeout(() => {
    if (!handled) onNoRedirect()
  }, 20000)

  return () => {
    handled = true
    unsubscribe()
    clearTimeout(timeout)
  }
}

export async function signupWithFirebaseEmail(email: string, pass: string) {
  if (!auth) {
    throw notConfiguredError('Firebase email signup')
  }
  const result = await createUserWithEmailAndPassword(auth, email, pass)
  try {
    await sendEmailVerification(result.user)
  } catch (e) {
    console.warn('[Firebase] Email verification send warning:', e)
  }
  const idToken = await result.user.getIdToken()
  return { user: result.user, idToken }
}

export async function loginWithFirebaseEmail(email: string, pass: string) {
  if (!auth) {
    throw notConfiguredError('Firebase email login')
  }
  const result = await signInWithEmailAndPassword(auth, email, pass)
  const idToken = await result.user.getIdToken()
  return { user: result.user, idToken }
}

/**
 * Null-safe wrapper around firebase/auth's signOut. Consumers pass the
 * (possibly null) `firebaseAuth` export; when Firebase isn't configured this
 * is a no-op so logout still clears the local session cleanly.
 */
export async function firebaseSignOut(authArg?: ReturnType<typeof getAuth> | null): Promise<void> {
  if (!authArg) return
  await signOut(authArg)
}

/**
 * Get a fresh Firebase ID token for the currently signed-in user.
 * Force-refreshes when `forceRefresh` is true (used on 401s). Returns null
 * when Firebase isn't configured or no user is signed in.
 */
export async function getCurrentIdToken(forceRefresh = false): Promise<string | null> {
  if (!auth?.currentUser) return null
  return auth.currentUser.getIdToken(forceRefresh)
}

/**
 * Upload an avatar image to Firebase Storage and return its download URL.
 */
export async function uploadAvatar(file: File): Promise<string> {
  if (!app || !auth) {
    throw notConfiguredError('Avatar upload')
  }
  const storage = getStorage(app)
  const uid = auth.currentUser?.uid || 'anonymous'
  const ext = (file.name.split('.').pop() || 'png').replace(/[^a-zA-Z0-9]/g, '')
  const storageRef = ref(storage, `avatars/${uid}-${Date.now()}.${ext}`)
  const snapshot = await uploadBytes(storageRef, file)
  return getDownloadURL(snapshot.ref)
}

/**
 * Change the user's password. Passwords are owned by Firebase Auth — the
 * backend no longer stores them. Requires the current password to re-auth.
 */
export async function changeFirebasePassword(currentPassword: string, newPassword: string): Promise<void> {
  if (!auth?.currentUser?.email) {
    throw notConfiguredError('Password change')
  }
  const credential = EmailAuthProvider.credential(auth.currentUser.email, currentPassword)
  await reauthenticateWithCredential(auth.currentUser, credential)
  await updatePassword(auth.currentUser, newPassword)
}

export {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendEmailVerification,
  googleProvider,
  updatePassword,
  reauthenticateWithCredential,
  EmailAuthProvider,
}
export type { FirebaseUser }
