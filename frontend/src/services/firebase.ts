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
  signOut,
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

/**
 * Firebase is OPTIONAL. When the VITE_FIREBASE_* env vars aren't present
 * (CI, or a deploy that skips Firebase), the app still works fully:
 *
 *   • Email/password login & registration run through the backend API
 *     (POST /api/v1/auth/login, /api/v1/auth/register) — no Firebase needed.
 *   • Google Sign-In and Firebase-verified signup degrade gracefully with a
 *     clear error instead of crashing the whole SPA at module load.
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
// Used to distinguish "returning from Google redirect" from "normal page load".
// Without this, onAuthStateChanged fires with a cached Firebase user on every
// page load, causing an infinite redirect loop.
const REDIRECT_FLAG = 'agentos_google_redirect'

/**
 * Initiates Google Sign-In via same-tab redirect (no popup window).
 * Sets a sessionStorage flag so the login page knows to process the result.
 */
export async function loginWithGoogle(): Promise<void> {
  if (!auth || !googleProvider) {
    throw notConfiguredError('Google Sign-In')
  }
  sessionStorage.setItem(REDIRECT_FLAG, '1')
  await signInWithRedirect(auth, googleProvider)
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
    // Sign out any lingering Firebase session so it doesn't interfere
    // (e.g., user logged out of our app but Firebase session persists)
    signOut(authRef).catch(() => {})
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

export {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendEmailVerification,
  googleProvider,
}
export type { FirebaseUser }
