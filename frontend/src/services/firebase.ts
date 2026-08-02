import { initializeApp, getApps, getApp } from 'firebase/app'
import {
  getAuth,
  GoogleAuthProvider,
  signInWithRedirect,
  getRedirectResult,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendEmailVerification,
  signOut as firebaseSignOut,
  User as FirebaseUser,
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
for (const key of requiredKeys) {
  if (!firebaseConfig[key]) {
    throw new Error(
      `[Firebase] Missing env var for "${key}". Set it in frontend/.env (dev) or deployment env (prod).`
    )
  }
}

const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp()
export const firebaseAuth = getAuth(app)
export const googleProvider = new GoogleAuthProvider()
googleProvider.setCustomParameters({ prompt: 'select_account' })

// ─── Session flag ────────────────────────────────────────────────────
// Used to distinguish "returning from Google redirect" from "normal page load".
// Without this, onAuthStateChanged fires with a cached Firebase user on every
// page load, causing an infinite redirect loop.
const REDIRECT_FLAG = 'agentos_google_redirect'

/**
 * Initiates Google Sign-In via same-tab redirect (no popup window).
 * Sets a sessionStorage flag so the login page knows to process the result.
 */
export async function loginWithGoogle(): Promise<void> {
  sessionStorage.setItem(REDIRECT_FLAG, '1')
  await signInWithRedirect(firebaseAuth, googleProvider)
}

/**
 * Check if we're returning from a Google redirect.
 * Call this on login/register page mount.
 *
 * Strategy:
 * 1. If no redirect flag → return null immediately (normal page load, no redirect loop)
 * 2. If flag is set → try getRedirectResult() first (works in Chrome/Firefox)
 * 3. If getRedirectResult() returns null (Safari ITP) → fall back to onAuthStateChanged
 * 4. Clear the flag after processing
 *
 * @returns { user, idToken } if a redirect sign-in just completed, null otherwise
 */
export function checkGoogleRedirect(
  onSuccess: (user: FirebaseUser, idToken: string) => void,
  onNoRedirect: () => void,
): () => void {
  // No flag = normal page load, not a redirect return
  if (!sessionStorage.getItem(REDIRECT_FLAG)) {
    // Sign out any lingering Firebase session so it doesn't interfere
    // (e.g., user logged out of our app but Firebase session persists)
    firebaseSignOut(firebaseAuth).catch(() => {})
    onNoRedirect()
    return () => {}
  }

  // Flag is set — we ARE returning from a Google redirect
  sessionStorage.removeItem(REDIRECT_FLAG)

  let handled = false

  // Try getRedirectResult first (works in Chrome/Firefox/Edge)
  getRedirectResult(firebaseAuth)
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
  const unsubscribe = onAuthStateChanged(firebaseAuth, async (user) => {
    if (handled) return
    if (user) {
      handled = true
      unsubscribe()
      const idToken = await user.getIdToken()
      onSuccess(user, idToken)
    }
  })

  // Safety timeout: if neither fires within 8s, give up and show the form
  const timeout = setTimeout(() => {
    if (!handled) {
      handled = true
      unsubscribe()
      onNoRedirect()
    }
  }, 8000)

  return () => {
    handled = true
    unsubscribe()
    clearTimeout(timeout)
  }
}

export async function signupWithFirebaseEmail(email: string, pass: string) {
  const result = await createUserWithEmailAndPassword(firebaseAuth, email, pass)
  try {
    await sendEmailVerification(result.user)
  } catch (e) {
    console.warn('[Firebase] Email verification send warning:', e)
  }
  const idToken = await result.user.getIdToken()
  return { user: result.user, idToken }
}

export async function loginWithFirebaseEmail(email: string, pass: string) {
  const result = await signInWithEmailAndPassword(firebaseAuth, email, pass)
  const idToken = await result.user.getIdToken()
  return { user: result.user, idToken }
}

export {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendEmailVerification,
  firebaseSignOut,
}
export type { FirebaseUser }
