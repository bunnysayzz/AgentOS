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
  sendPasswordResetEmail,
  signOut,
  User as FirebaseUser,
} from 'firebase/auth'
import { getStorage, ref, uploadBytes, getDownloadURL } from 'firebase/storage'
import {
  reauthenticateWithCredential,
  EmailAuthProvider,
  updatePassword,
  setPersistence,
  browserLocalPersistence,
} from 'firebase/auth'
import { useAuthStore } from '@/stores/authStore'

/**
 * Resolve the Firebase authDomain.
 *
 * Google sign-in is delivered through helper code on the authDomain, and the
 * OAuth popup asks Google to redirect back to
 * ``https://<authDomain>/__/auth/handler``. That redirect URI must be
 * REGISTERED on the project's OAuth web client in Google Cloud Console — the
 * default Firebase setup only registers the ``<project>.firebaseapp.com``
 * one. A live end-to-end browser probe (headless Chrome against the Render
 * site) proved that using the app's own hostname here makes Google reject
 * the popup with ``redirect_uri_mismatch`` (Error 400, "Access blocked: this
 * app's request is invalid") because the Render domain's handler URI is not
 * on the allow-list — login fails on EVERY browser, not just Safari.
 *
 * So we use exactly the value configured in VITE_FIREBASE_AUTH_DOMAIN and
 * never invent an origin. The backend still reverse-proxies /__/auth and
 * /__/firebase on the app origin (backend app/core/auth_proxy.py); once the
 * handler URI for the custom origin is added to the OAuth client in GCP
 * (Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client
 * IDs → Authorized redirect URIs), pointing VITE_FIREBASE_AUTH_DOMAIN at the
 * app's own domain makes the helper same-origin (ITP-safe) with no further
 * code changes.
 */
function resolveAuthDomain(): string {
  return (import.meta.env.VITE_FIREBASE_AUTH_DOMAIN as string | undefined)?.trim() || ''
}

const firebaseConfig = {
  apiKey:            import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain:        resolveAuthDomain(),
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
  // Explicit session persistence (browser localStorage). This is already the
  // SDK default, but declaring it guards against future default changes and
  // makes the intent obvious. Failures (private browsing, blocked storage)
  // fall back to the SDK default silently — the app still works, just
  // without a remembered session.
  setPersistence(auth, browserLocalPersistence).catch(() => {})
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
 * Browsers with NO popup support at all: iOS in-app browsers (Instagram,
 * Facebook, DuckDuckGo…) wrap WKWebView, which blocks window.open entirely,
 * so Google sign-in must use the same-tab redirect flow there.
 *
 * Real Safari (desktop + iOS) is deliberately NOT matched — it carries a
 * "Safari/" UA token, and the popup flow DOES work there (the popup opens in
 * a tab in small windows; in fullscreen it can open a separate window and
 * fail with auth/internal-error, which the popup retry + redirect fallback
 * below handle). Going redirect-only on Safari is strictly worse: Safari's
 * ITP blocks the cross-origin result exchange (auth domain ≠ app origin), so
 * the redirect return never completes and the user is stuck on the login
 * page with a poisoned pending-redirect state.
 */
function isInAppBrowser(): boolean {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent
  return /applewebkit/i.test(ua) && /mobile/i.test(ua) && !/safari\//i.test(ua)
}

/**
 * Real Safari (desktop + iOS) — distinguishable from Chrome/Firefox/Edge
 * (whose UAs also carry a Safari/ token) and from iOS in-app browsers.
 */
function isRealSafari(): boolean {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent
  return /safari\//i.test(ua) && !/chrome\/|crios|fxios|edg\/|chromium|headless/i.test(ua)
}

// ─── Benign SDK rejection guard ─────────────────────────────────────────
// The Firebase SDK rejects promises with "Database is closing/hidden" from
// its IndexedDB layer whenever a background write races with the tab being
// hidden (popup sign-in stealing focus, tab switches, page unload). These
// rejections are harmless and never affect app state — swallow them globally
// so they don't pollute the console or trip error monitors. Installed once.
const windowWithGuard = typeof window !== 'undefined'
  ? (window as unknown as { __agentosFirebaseRejectionGuard?: boolean })
  : null
if (windowWithGuard && !windowWithGuard.__agentosFirebaseRejectionGuard) {
  windowWithGuard.__agentosFirebaseRejectionGuard = true
  window.addEventListener('unhandledrejection', (event) => {
    const message = (event.reason as Error | undefined)?.message || String(event.reason || '')
    if (/Database is (closing|hidden)|database connection is closing/i.test(message)) {
      event.preventDefault()
    }
  })
}

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

  // iOS in-app browsers (WKWebView) block popups entirely — go straight to
  // the same-tab redirect flow there. Every other browser (including Safari)
  // is popup-first: Safari's popup works in normal windows/tabs, and the
  // retry + redirect fallback below covers the fullscreen-window failure.
  if (isInAppBrowser()) {
    sessionStorage.setItem(REDIRECT_FLAG, '1')
    await signInWithRedirect(auth, googleProvider)
    return null
  }

  // Chrome/Firefox/Edge: popup-first. Safari (esp. fullscreen) intermittently
  // fails the popup↔iframe postMessage handshake, which the SDK wraps as the
  // generic auth/internal-error — a popup-plumbing failure, never a
  // credential problem. The first attempt warms the auth iframe, so retry
  // ONCE before falling back to the redirect flow: this converts many
  // one-off failures into instant successes (and avoids the redirect
  // return-trip entirely).
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const result = await signInWithPopup(auth, googleProvider)
      const idToken = await result.user.getIdToken()
      return { user: result.user, idToken }
    } catch (err: unknown) {
      const e = err as { code?: string; message?: string } | undefined
      const code = e?.code || ''
      const message = e?.message || ''

      // The Firebase SDK's IndexedDB layer throws "Database is closing/hidden"
      // (a message-only error with NO code) when a background storage write
      // races with the tab being hidden — exactly what happens when a sign-in
      // popup steals focus on desktop Safari/fullscreen. Never a real failure.
      const hiddenTabStorageError = !code && /Database is (closing|hidden)/i.test(message)

      // Stale pending-redirect self-heal: a previous redirect return that
      // never completed (Safari ITP swallowing the cross-origin result) leaves
      // the SDK's "firebase:redirect_user:<apiKey>" sessionStorage key behind.
      // EVERY subsequent sign-in attempt — popup included — then throws
      // auth/redirect-operation-pending, which is exactly the "stuck on the
      // login page" symptom. Consume the stale state; if a valid result is
      // actually waiting, the sign-in already completed and we return it.
      if (code === 'auth/redirect-operation-pending') {
        const pending = await consumePendingRedirect(auth)
        if (pending) return pending
        // State cleared — the popup was never really attempted; retry once.
        if (attempt === 1) continue
      }

      // Transient popup-plumbing failures: retry once, then fall back below.
      if (attempt === 1 && (code === 'auth/internal-error' || hiddenTabStorageError)) {
        continue
      }

      const popupUnavailable = [
        'auth/popup-blocked',
        'auth/operation-not-supported-in-this-environment',
        'auth/cancelled-popup-request',
        'auth/internal-error',
        'auth/redirect-operation-pending',
      ]
      if (popupUnavailable.includes(code) || hiddenTabStorageError) {
        // Real Safari: NEVER fall back to the same-tab redirect. Safari's ITP
        // blocks the cross-origin result exchange (auth domain ≠ app origin),
        // so the redirect return never completes and leaves a poisoned
        // pending-redirect state behind — the "stuck on the login page"
        // symptom. The popup DOES work in normal Safari windows/tabs; when it
        // fails (fullscreen opens the popup in a separate window that Apple
        // blocks), surface a clear actionable message instead of starting a
        // broken redirect. This matches the project's Firebase docs guidance:
        // non-Firebase hosting must use the popup, and the permanent fix is
        // the same-origin auth-helper proxy (backend /__/auth) + the OAuth
        // client redirect URI.
        if (isRealSafari()) {
          throw new Error(
            'Google sign-in was blocked by Safari. Please try again in a smaller Safari window, use Chrome, Firefox or Edge, or sign in with email & password below.',
          )
        }
        // Popup not possible → same-tab redirect. checkGoogleRedirect()
        // completes the sign-in when the user returns.
        sessionStorage.setItem(REDIRECT_FLAG, '1')
        try {
          await signInWithRedirect(auth, googleProvider)
        } catch (redirectErr) {
          const redirectCode = (redirectErr as { code?: string })?.code || ''
          // Another stale pending redirect blocked the START of this one —
          // consume it, then retry the redirect once.
          if (redirectCode === 'auth/redirect-operation-pending') {
            await consumePendingRedirect(auth)
            await signInWithRedirect(auth, googleProvider)
            return null
          }
          // Starting the redirect can fail while the browser is still mid-flight
          // with the popup it just opened. When the root cause was the benign
          // hidden-tab error, rethrow THAT so the UI takes the graceful "show
          // the form again" path instead of a confusing redirect banner.
          if (hiddenTabStorageError) throw err
          throw redirectErr
        }
        return null
      }
      throw err
    }
  }
  // Unreachable: every path above returns or throws.
  return null
}

/**
 * Map a Firebase user to the optimistic store profile. Used for instant
 * hydration before the backend /auth/me refines it with the full profile.
 */
export function firebaseUserToStoreUser(user: FirebaseUser): {
  id: string
  email: string
  username: string
  fullName: string
  avatarUrl?: string
} {
  return {
    id: user.uid,
    email: user.email || '',
    username: user.displayName || '',
    fullName: user.displayName || 'User',
    avatarUrl: user.photoURL || undefined,
  }
}

/**
 * Keep the persisted auth store reconciled with Firebase Auth — the single
 * source of truth. Call once at app boot (main.tsx).
 *
 * - Boot: if Firebase reports a signed-in user but the store is empty
 *   (stale/cleared persistence), hydrate the store from the real session.
 * - Sign-out anywhere: if Firebase reports NO session but the store thinks
 *   it is authenticated (revoked token, sign-out in another tab), clear it
 *   — this gives cross-tab logout sync for free. A short grace period
 *   avoids the logged-out flicker when Firebase asynchronously restores a
 *   valid session on boot.
 * - Guests: no Firebase session and no stored token → untouched.
 *
 * @returns an unsubscribe function, or null when Firebase isn't configured.
 */
export function attachAuthStateSync(): (() => void) | null {
  if (!auth) return null
  const authRef = auth
  let clearTimer: ReturnType<typeof setTimeout> | null = null

  return onAuthStateChanged(authRef, (user) => {
    const { accessToken, clearAuth, setAuth } = useAuthStore.getState()

    if (user) {
      // A session arrived — cancel any pending clear.
      if (clearTimer) {
        clearTimeout(clearTimer)
        clearTimer = null
      }
      // Only hydrate when the store has no session (don't clobber a fresh
      // login's optimistic profile with the coarser Firebase profile).
      if (!accessToken) {
        user
          .getIdToken()
          .then((idToken) => {
            // Apply only if nobody signed in meanwhile (a ghost setAuth
            // self-heals anyway — the next onAuthStateChanged(null) clears it).
            if (useAuthStore.getState().accessToken) return
            setAuth(idToken, '', firebaseUserToStoreUser(user))
          })
          .catch(() => {
            // Token fetch can transiently fail while the tab is hidden —
            // the store is fine as-is; a later state change re-syncs.
          })
      }
    } else if (accessToken) {
      // Firebase says there is no session but the store claims otherwise:
      // revoked/expired session, or sign-out from another tab. Wait briefly
      // in case Firebase is still restoring a valid session on boot.
      if (clearTimer) clearTimeout(clearTimer)
      clearTimer = setTimeout(() => {
        clearTimer = null
        if (!useAuthStore.getState().accessToken) return
        clearAuth()
        localStorage.removeItem('agentos-auth')
      }, 1250)
    }
  })
}

/**
 * Consume the SDK's pending-redirect state.
 *
 * A redirect return that never completed (Safari ITP swallowing the
 * cross-origin result) leaves "firebase:redirect_user:<apiKey>" in
 * sessionStorage. Every later sign-in attempt — popup or redirect — then
 * throws auth/redirect-operation-pending, stranding the user on the login
 * page with no way forward. Calling getRedirectResult() clears that state,
 * and returns the user when a valid result IS waiting.
 */
async function consumePendingRedirect(
  authRef: ReturnType<typeof getAuth>,
): Promise<{ user: FirebaseUser; idToken: string } | null> {
  try {
    const result = await getRedirectResult(authRef)
    if (result) {
      const idToken = await result.user.getIdToken()
      return { user: result.user, idToken }
    }
  } catch {
    // Stale/expired — getRedirectResult already cleared it.
  }
  return null
}

/**
 * Check if we're returning from a Google redirect (the popup fallback path).
 * Call this on login/register page mount.
 *
 * Strategy:
 * 1. Always call getRedirectResult() — even when our redirect flag is
 *    absent. This (a) completes the normal return trip in Chrome/FF/Edge,
 *    (b) self-heals a stale pending-redirect left by a broken Safari return
 *    (the "stuck on login page" state), and (c) completes an orphaned result
 *    (page reloaded before the result landed).
 * 2. Redirect flag set → keep showing the spinner while getRedirectResult /
 *    onAuthStateChanged resolve, bounded by 8s; on timeout show the form and
 *    (when provided) fire onTimeout with a helpful message.
 * 3. No flag → normal page load: show the form immediately once
 *    getRedirectResult settles empty.
 *
 * @returns an unsubscribe/cleanup function for the effect.
 */
export function checkGoogleRedirect(
  onSuccess: (user: FirebaseUser, idToken: string) => void,
  onNoRedirect: () => void,
  onTimeout?: () => void,
): () => void {
  // Firebase not configured → Google auth isn't possible; just show the form.
  if (!auth) {
    onNoRedirect()
    return () => {}
  }
  // Capture a const so TypeScript keeps the narrowing inside the closures
  // below (a module-level `let` is not narrowed inside callbacks).
  const authRef = auth

  const returningFromRedirect = sessionStorage.getItem(REDIRECT_FLAG)
  if (returningFromRedirect) {
    sessionStorage.removeItem(REDIRECT_FLAG)
  }

  let handled = false

  // Always call getRedirectResult: normal return trip in Chrome/Firefox/Edge,
  // self-heal of stale pending-redirect state (Safari ITP), and completion of
  // orphaned results — see the function docstring.
  getRedirectResult(authRef)
    .then(async (result) => {
      if (handled) return
      if (result) {
        handled = true
        const idToken = await result.user.getIdToken()
        onSuccess(result.user, idToken)
      } else if (!returningFromRedirect) {
        // Normal page load with no pending result → show the form right away.
        handled = true
        onNoRedirect()
      }
      // returningFromRedirect + null result → Safari ITP likely swallowed it;
      // wait for the onAuthStateChanged fallback below (or the timeout).
    })
    .catch(() => {
      // getRedirectResult error — the onAuthStateChanged fallback handles the
      // redirect-return case; a normal load just shows the form.
      if (!returningFromRedirect && !handled) {
        handled = true
        onNoRedirect()
      }
    })

  // Fallback: onAuthStateChanged (catches the Safari ITP case where
  // getRedirectResult returns null but the session actually exists).
  const unsubscribe = onAuthStateChanged(authRef, async (user) => {
    if (handled) return
    if (user) {
      handled = true
      unsubscribe()
      const idToken = await user.getIdToken()
      onSuccess(user, idToken)
    }
  })

  // The redirect return trip is normally fast (IndexedDB + token restore).
  // If nothing has completed after 8s, show the form — but KEEP the listener
  // alive so a late sign-in result is still consumed (no lost logins). 8s is
  // long enough for real returns and short enough that users never stare at
  // the spinner for a lost/blocked redirect (Safari ITP etc.). onTimeout lets
  // the page explain WHAT went wrong instead of silently restoring the form.
  let timeout: ReturnType<typeof setTimeout> | null = null
  if (returningFromRedirect) {
    timeout = setTimeout(() => {
      if (!handled) {
        if (onTimeout) {
          onTimeout()
        } else {
          onNoRedirect()
        }
      }
    }, 8000)
  }

  return () => {
    handled = true
    unsubscribe()
    if (timeout) clearTimeout(timeout)
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
 * Send a password-reset email for an existing account (forgot-password flow).
 * Throws auth/… codes the UI maps to friendly messages. Unknown emails throw
 * auth/user-not-found — callers should treat that as success to avoid
 * revealing which accounts exist.
 */
export async function sendPasswordResetEmailWrapper(email: string): Promise<void> {
  if (!auth) {
    throw notConfiguredError('Password reset')
  }
  await sendPasswordResetEmail(auth, email)
}

/**
 * (Re)send the email-verification link to the signed-in user.
 */
export async function resendVerificationEmail(): Promise<void> {
  if (!auth?.currentUser) {
    throw notConfiguredError('Email verification')
  }
  await sendEmailVerification(auth.currentUser)
}

/**
 * Reload the signed-in Firebase user and return its live verification state.
 * Used by the verify-email screen to detect the click on the verification
 * link without a manual page refresh. Returns null when no user is signed in.
 */
export async function reloadFirebaseUser(): Promise<{ email: string; emailVerified: boolean } | null> {
  if (!auth?.currentUser) return null
  await auth.currentUser.reload()
  const user = auth.currentUser
  return { email: user?.email || '', emailVerified: !!user?.emailVerified }
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
 * Best-effort delete of the user's avatar from Firebase Storage.
 * Called during account deletion so the file doesn't outlive the account.
 * Failures are swallowed — the profile doc is the source of truth.
 */
export async function deleteAvatar(): Promise<void> {
  if (!app || !auth?.currentUser) return
  try {
    const storage = getStorage(app)
    const uid = auth.currentUser.uid
    // Avatar files live at avatars/<uid>-<timestamp>.<ext>. Listing the uid
    // prefix and deleting each child removes them all.
    const { listAll, deleteObject } = await import('firebase/storage')
    const items = await listAll(ref(storage, `avatars/${uid}`))
    await Promise.all(items.items.map((item) => deleteObject(item)))
  } catch {
    // Best-effort only — never block account deletion on storage cleanup.
  }
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
  sendPasswordResetEmail,
  googleProvider,
  updatePassword,
  reauthenticateWithCredential,
  EmailAuthProvider,
}
export type { FirebaseUser }
