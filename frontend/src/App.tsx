import { Routes, Route } from 'react-router-dom'
import Layout from '@/components/Layout'
import ProtectedRoute from '@/components/ProtectedRoute'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import Dashboard from '@/pages/Dashboard'
import Workspaces from '@/pages/Workspaces'
import WorkspaceDetail from '@/pages/WorkspaceDetail'
import Agents from '@/pages/Agents'
import Workflows from '@/pages/Workflows'
import Tools from '@/pages/Tools'
import Prompts from '@/pages/Prompts'
import Secrets from '@/pages/Secrets'
import Artifacts from '@/pages/Artifacts'
import Memory from '@/pages/Memory'
import MCPGateway from '@/pages/MCPGateway'
import Telemetry from '@/pages/Telemetry'
import ExecutionGraphs from '@/pages/ExecutionGraphs'
import Providers from '@/pages/Providers'
import Profile from '@/pages/Profile'
import ApiKeys from '@/pages/ApiKeys'

function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

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
          <Route path="/secrets" element={<Secrets />} />
          <Route path="/artifacts" element={<Artifacts />} />
          <Route path="/memory" element={<Memory />} />
          <Route path="/mcp" element={<MCPGateway />} />
          <Route path="/telemetry" element={<Telemetry />} />
          <Route path="/graphs" element={<ExecutionGraphs />} />
          <Route path="/providers" element={<Providers />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/api-keys" element={<ApiKeys />} />
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
