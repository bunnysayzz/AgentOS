import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

const seen: string[] = []
;(globalThis as any).__AX_SEEN__ = seen

// ─── Global axios mock (single source of truth) ─────────────────────────
// Two test files (api.test.ts, Login.test.tsx) need axios mocked. Registering
// the mock HERE — instead of per-file — avoids Vitest's worker-level CJS mock
// collision, where only the first vi.mock('axios') factory runs and later
// files silently get a stale/foreign mock. Because the factory is identical
// for every file, the shared registration is harmless.
//
// The fake instance is exposed on `globalThis.__AX__` so tests can reach the
// captured interceptor handlers and stub instance methods.
vi.mock('axios', () => {
  const makeInstance = () => {
    const reqHandlers: any[] = []
    const respErrHandlers: any[] = []
    const instance = Object.assign(vi.fn(), {
      interceptors: {
        request: { use: (h: any) => reqHandlers.push(h) },
        response: { use: (_h: any, errH: any) => respErrHandlers.push(errH) },
      },
      reqHandlers,
      respErrHandlers,
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      patch: vi.fn(),
      delete: vi.fn(),
      defaults: { headers: { common: {} } },
    })
    return instance
  }
  // The instance created by `axios.create()` is attached to the mocked
  // default export itself (`__AX__`), because the same module object is
  // shared between this factory and the importing test file — unlike
  // globalThis, which can differ between the setup and test contexts.
  seen.push('factory-ran')
  const fakeDefault: any = {
    create: () => {
      seen.push('create-called')
      const inst = makeInstance()
      fakeDefault.__AX__ = inst
      return inst
    },
    post: vi.fn(),
    get: vi.fn(),
    __AX__: null,
  }
  return {
    default: fakeDefault,
    AxiosError: class AxiosError extends Error {
      config: any
      response: any
      constructor(message: string, _code?: string, config?: any) {
        super(message)
        this.config = config
      }
    },
  }
})

// ─── Firebase stub (single source of truth) ─────────────────────────────
// api.ts and the auth pages import from '@/services/firebase'. The real
// module throws at import time when env vars are missing, so every test
// file must see a stub. Union of everything the tests rely on.
vi.mock('@/services/firebase', () => ({
  firebaseAuth: {},
  googleProvider: {},
  firebaseSignOut: vi.fn().mockResolvedValue(undefined),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  sendEmailVerification: vi.fn(),
  loginWithGoogle: vi.fn().mockResolvedValue({ user: {}, idToken: 'google-id-token' }),
  firebaseUserToStoreUser: vi.fn((user: any) => ({
    id: user?.uid || '',
    email: user?.email || '',
    username: user?.displayName || '',
    fullName: user?.displayName || 'User',
    avatarUrl: user?.photoURL || undefined,
  })),
  checkGoogleRedirect: vi.fn((_onSuccess: unknown, onNoRedirect: () => void) => {
    onNoRedirect()
    return () => {}
  }),
  signupWithFirebaseEmail: vi.fn(),
  loginWithFirebaseEmail: vi.fn(),
  getCurrentIdToken: vi.fn().mockResolvedValue('fresh-id-token'),
  uploadAvatar: vi.fn().mockResolvedValue('https://storage.example/avatar.png'),
  changeFirebasePassword: vi.fn().mockResolvedValue(undefined),
  sendPasswordResetEmail: vi.fn(),
  sendPasswordResetEmailWrapper: vi.fn(),
  resendVerificationEmail: vi.fn(),
  reloadFirebaseUser: vi.fn(),
  isFirebaseConfigured: true,
}))

// ─── jsdom polyfills ─────────────────────────────────────────────────────
// jsdom does not implement ResizeObserver or scrollIntoView; polyfill so
// components that use them (e.g. scroll-to-bottom in chat) don't crash tests.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.stubGlobal('ResizeObserver', ResizeObserverStub)

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn()
}

// jsdom in this Vitest version does not expose localStorage/sessionStorage.
// The app (Zustand persistence, Google-redirect flag) depends on them, so
// provide an in-memory Storage implementation for the whole test run.
class MemoryStorage implements Storage {
  private store = new Map<string, string>()

  get length(): number {
    return this.store.size
  }

  clear(): void {
    this.store.clear()
  }

  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key)! : null
  }

  key(index: number): string | null {
    return [...this.store.keys()][index] ?? null
  }

  removeItem(key: string): void {
    this.store.delete(key)
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value))
  }
}

const memoryStorage = new MemoryStorage()
vi.stubGlobal('localStorage', memoryStorage)
vi.stubGlobal('sessionStorage', memoryStorage)
