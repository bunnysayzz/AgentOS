import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as Sentry from '@sentry/react'
import App from './App'
import { attachAuthStateSync } from '@/services/firebase'
import './index.css'

// ─── Error tracking (env-gated) ────────────────────────────────────────
// Set VITE_SENTRY_DSN to enable crash reporting. Without it, this is a
// complete no-op — local dev and CI are untouched.
const sentryDsn = import.meta.env.VITE_SENTRY_DSN as string | undefined
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: import.meta.env.PROD ? 'production' : 'development',
    tracesSampleRate: 0.1,
    // Never send auth tokens or API keys (axios headers excluded by default
    // unless explicitly instrumented with sendDefaultPii).
    sendDefaultPii: false,
  })
}

// ─── Privacy-friendly analytics (env-gated) ───────────────────────────
// Set VITE_ANALYTICS_URL (e.g. your Plausible/Umami instance script URL) to
// enable pageview tracking. Cookies-free by design — no consent banner
// needed in most EU interpretations when the provider is cookie-less.
const analyticsUrl = import.meta.env.VITE_ANALYTICS_URL as string | undefined
if (analyticsUrl) {
  const s = document.createElement('script')
  s.defer = true
  s.src = analyticsUrl
  document.head.appendChild(s)
}

// Firebase Auth is the single source of truth for sessions: reconcile the
// persisted store at boot and keep it in sync across tabs (sign-out in one
// tab signs out everywhere). No-op when Firebase isn't configured.
attachAuthStateSync()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>,
)
