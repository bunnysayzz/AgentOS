import { lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from '@/components/Layout'
import ProtectedRoute from '@/components/ProtectedRoute'
import RequireAuth from '@/components/RequireAuth'

// Route-level code splitting: each page ships in its own chunk and loads on
// first visit, so the initial bundle stays small. The shell (Layout,
// Sidebar, auth guards) stays eager.
const Login = lazy(() => import('@/pages/Login'))
const Register = lazy(() => import('@/pages/Register'))
const VerifyEmail = lazy(() => import('@/pages/VerifyEmail'))
const ForgotPassword = lazy(() => import('@/pages/ForgotPassword'))
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const Workspaces = lazy(() => import('@/pages/Workspaces'))
const WorkspaceDetail = lazy(() => import('@/pages/WorkspaceDetail'))
const Agents = lazy(() => import('@/pages/Agents'))
const Workflows = lazy(() => import('@/pages/Workflows'))
const Tools = lazy(() => import('@/pages/Tools'))
const Prompts = lazy(() => import('@/pages/Prompts'))
const Secrets = lazy(() => import('@/pages/Secrets'))
const Artifacts = lazy(() => import('@/pages/Artifacts'))
const Memory = lazy(() => import('@/pages/Memory'))
const MCPGateway = lazy(() => import('@/pages/MCPGateway'))
const Telemetry = lazy(() => import('@/pages/Telemetry'))
const ExecutionGraphs = lazy(() => import('@/pages/ExecutionGraphs'))
const Providers = lazy(() => import('@/pages/Providers'))
const Profile = lazy(() => import('@/pages/Profile'))
const ApiKeys = lazy(() => import('@/pages/ApiKeys'))
const Terms = lazy(() => import('@/pages/Terms'))
const Privacy = lazy(() => import('@/pages/Privacy'))
const Gallery = lazy(() => import('@/pages/Gallery'))
const Budget = lazy(() => import('@/pages/Budget'))
const WebhookDebugger = lazy(() => import('@/pages/WebhookDebugger'))
const Evaluations = lazy(() => import('@/pages/Evaluations'))
const ABTesting = lazy(() => import('@/pages/ABTesting'))
const IaC = lazy(() => import('@/pages/IaC'))

function App() {
  return (
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/gallery" element={<Gallery />} />

        {/* Protected routes */}
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/workspaces" element={<Workspaces />} />
            <Route path="/workspaces/:workspaceId" element={<WorkspaceDetail />} />
            <Route path="/workspaces/:workspaceId/agents" element={<Agents />} />
            <Route path="/workspaces/:workspaceId/workflows" element={<Workflows />} />
            <Route path="/workspaces/:workspaceId/tools" element={<Tools />} />
            <Route path="/workspaces/:workspaceId/prompts" element={<Prompts />} />
            <Route path="/workspaces/:workspaceId/secrets" element={<Secrets />} />
            <Route path="/workspaces/:workspaceId/artifacts" element={<Artifacts />} />
            <Route path="/workspaces/:workspaceId/memory" element={<Memory />} />
            <Route path="/workspaces/:workspaceId/telemetry" element={<Telemetry />} />
            <Route path="/workspaces/:workspaceId/graphs" element={<ExecutionGraphs />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/workflows" element={<Workflows />} />
            <Route path="/tools" element={<Tools />} />
            <Route path="/prompts" element={<Prompts />} />
            <Route path="/artifacts" element={<Artifacts />} />
            <Route path="/memory" element={<Memory />} />
            <Route path="/mcp" element={<MCPGateway />} />
            <Route path="/telemetry" element={<Telemetry />} />
            <Route path="/graphs" element={<ExecutionGraphs />} />

            {/* Account & security pages — require a signed-in user. Guests are
                redirected to /login?redirect=<target> and return after auth. */}
            <Route element={<RequireAuth />}>
              <Route path="/profile" element={<Profile />} />
              <Route path="/api-keys" element={<ApiKeys />} />
              <Route path="/secrets" element={<Secrets />} />
              <Route path="/workspaces/:workspaceId/secrets" element={<Secrets />} />
              <Route path="/providers" element={<Providers />} />
              <Route path="/budget" element={<Budget />} />
              <Route path="/webhook-debugger" element={<WebhookDebugger />} />
              <Route path="/evaluations" element={<Evaluations />} />
              <Route path="/workspaces/:workspaceId/evaluations" element={<Evaluations />} />
              <Route path="/ab-testing" element={<ABTesting />} />
              <Route path="/workspaces/:workspaceId/ab-testing" element={<ABTesting />} />
              <Route path="/iac" element={<IaC />} />
              <Route path="/workspaces/:workspaceId/iac" element={<IaC />} />
            </Route>
          </Route>
        </Route>

        {/* 404 */}
        <Route
          path="*"
          element={
            <div className="min-h-screen flex flex-col items-center justify-center bg-surface-950 gap-4">
              <h1 className="text-5xl font-bold text-surface-700">404</h1>
              <p className="text-surface-500 text-lg">Page not found</p>
              <a href="/" className="btn-primary mt-2">Go home</a>
            </div>
          }
        />
      </Routes>
  )
}

export default App
