import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  DollarSignIcon, AlertTriangleIcon, ShieldIcon, TrendingUpIcon,
  MailIcon, SaveIcon,
} from '@/components/Icons'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import WorkspaceSelector from '@/components/WorkspaceSelector'
import WorkspaceRequired from '@/components/WorkspaceRequired'
import { toast } from '@/components/Toast'
import { cn } from '@/utils/cn'

interface BudgetSettings {
  monthly_limit_usd: number | null
  daily_limit_usd: number | null
  alert_threshold_pct: number
  hard_limit: boolean
  alert_emails: string[]
  alert_webhook: string | null
}

interface CostData {
  total_cost_usd: number
  total_calls: number
  total_tokens: number
  by_model: Record<string, { calls: number; tokens: number; cost_usd: number }>
}

interface BudgetCheck {
  budget: BudgetSettings
  monthly: CostData
  daily: CostData
  alerts: Array<{ type: string; limit: number; current: number; pct: number }>
  blocked: boolean
}

export default function Budget() {
  const qc = useQueryClient()
  const { workspaceId: paramWsId } = useParams<{ workspaceId?: string }>()
  const storeWsId = useWorkspaceStore((s) => s.selectedWorkspaceId)
  const wsId = paramWsId || storeWsId
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<BudgetSettings>({
    monthly_limit_usd: null,
    daily_limit_usd: null,
    alert_threshold_pct: 80,
    hard_limit: false,
    alert_emails: [],
    alert_webhook: null,
  })
  const [newEmail, setNewEmail] = useState('')

  const { data: budgetData, isLoading } = useQuery({
    queryKey: ['budget', wsId],
    queryFn: () => api.get(`/workspaces/${wsId}/budget`).then((r) => r.data),
    enabled: !!wsId,
  })

  const { data: monthlyCosts } = useQuery({
    queryKey: ['budget-costs', wsId, 'monthly'],
    queryFn: () => api.get(`/workspaces/${wsId}/budget/costs?period=monthly`).then((r) => r.data),
    enabled: !!wsId,
  })

  const { data: dailyCosts } = useQuery({
    queryKey: ['budget-costs', wsId, 'daily'],
    queryFn: () => api.get(`/workspaces/${wsId}/budget/costs?period=daily`).then((r) => r.data),
    enabled: !!wsId,
  })

  const { mutate: updateBudget, isPending } = useMutation({
    mutationFn: (data: Partial<BudgetSettings>) =>
      api.patch(`/workspaces/${wsId}/budget`, data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['budget', wsId] })
      toast.success('Budget updated', 'Your budget settings have been saved.')
      setEditing(false)
    },
    onError: (err: any) => toast.error('Update failed', err?.response?.data?.detail),
  })

  const budget: BudgetCheck | null = budgetData
  const monthly: CostData | null = monthlyCosts
  const daily: CostData | null = dailyCosts

  if (!wsId) return <WorkspaceRequired title="Budget" description="Select a workspace to manage budgets" />

  const monthlyLimit = budget?.budget?.monthly_limit_usd
  const dailyLimit = budget?.budget?.daily_limit_usd
  const monthlyPct = monthlyLimit && monthly ? (monthly.total_cost_usd / monthlyLimit) * 100 : 0
  const dailyPct = dailyLimit && daily ? (daily.total_cost_usd / dailyLimit) * 100 : 0

  const startEdit = () => {
    setForm(budget?.budget || form)
    setEditing(true)
  }

  const addEmail = () => {
    if (newEmail && newEmail.includes('@')) {
      setForm({ ...form, alert_emails: [...form.alert_emails, newEmail] })
      setNewEmail('')
    }
  }

  const removeEmail = (email: string) => {
    setForm({ ...form, alert_emails: form.alert_emails.filter((e) => e !== email) })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Budget & Cost Alerts</h1>
          <p className="text-surface-400 text-sm mt-1">Set spending limits and get notified when approaching them</p>
        </div>
        <div className="flex items-center gap-3">
          <WorkspaceSelector />
          {!editing && (
            <button onClick={startEdit} className="btn-primary flex items-center gap-2">
              <DollarSignIcon size={16} />Configure Budget
            </button>
          )}
        </div>
      </div>

      {/* Alerts Banner */}
      {budget?.alerts && budget.alerts.length > 0 && (
        <div className={cn(
          'p-4 rounded-xl border',
          budget.blocked ? 'bg-red-500/10 border-red-500/30' : 'bg-amber-500/10 border-amber-500/30',
        )}>
          <div className="flex items-center gap-3">
            <AlertTriangleIcon size={20} className={budget.blocked ? 'text-red-400' : 'text-amber-400'} />
            <div>
              <p className={cn('font-medium', budget.blocked ? 'text-red-300' : 'text-amber-300')}>
                {budget.blocked ? 'Budget exceeded — calls blocked' : 'Budget warning'}
              </p>
              {budget.alerts.map((alert, i) => (
                <p key={i} className="text-sm text-surface-400 mt-1">
                  {alert.type.includes('monthly') ? 'Monthly' : 'Daily'}: ${alert.current.toFixed(4)} / ${alert.limit} ({alert.pct}%)
                </p>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Cost Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card">
          <DollarSignIcon size={18} className="text-emerald-400 mb-2" />
          <p className="text-2xl font-bold">${monthly?.total_cost_usd?.toFixed(4) || '0'}</p>
          <p className="text-xs text-surface-500">This Month</p>
        </div>
        <div className="card">
          <DollarSignIcon size={18} className="text-amber-400 mb-2" />
          <p className="text-2xl font-bold">${daily?.total_cost_usd?.toFixed(4) || '0'}</p>
          <p className="text-xs text-surface-500">Today</p>
        </div>
        <div className="card">
          <TrendingUpIcon size={18} className="text-blue-400 mb-2" />
          <p className="text-2xl font-bold">{monthly?.total_calls || 0}</p>
          <p className="text-xs text-surface-500">Calls This Month</p>
        </div>
        <div className="card">
          <ShieldIcon size={18} className={budget?.blocked ? 'text-red-400 mb-2' : 'text-emerald-400 mb-2'} />
          <p className="text-2xl font-bold">{budget?.blocked ? 'BLOCKED' : 'Active'}</p>
          <p className="text-xs text-surface-500">Budget Status</p>
        </div>
      </div>

      {/* Monthly Usage Bar */}
      {monthlyLimit && (
        <div className="glass-panel p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium flex items-center gap-2">
              <TrendingUpIcon size={16} className="text-primary-400" />
              Monthly Usage
            </h3>
            <span className="text-sm text-surface-400">
              ${monthly?.total_cost_usd?.toFixed(4) || '0'} / ${monthlyLimit}
            </span>
          </div>
          <div className="h-3 rounded-full bg-surface-800 overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-500',
                monthlyPct >= 100 ? 'bg-red-500' : monthlyPct >= 80 ? 'bg-amber-500' : 'bg-emerald-500',
              )}
              style={{ width: `${Math.min(monthlyPct, 100)}%` }}
            />
          </div>
          <p className="text-xs text-surface-500 mt-2">{monthlyPct.toFixed(1)}% used</p>
        </div>
      )}

      {/* Daily Usage Bar */}
      {dailyLimit && (
        <div className="glass-panel p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium flex items-center gap-2">
              <TrendingUpIcon size={16} className="text-amber-400" />
              Daily Usage
            </h3>
            <span className="text-sm text-surface-400">
              ${daily?.total_cost_usd?.toFixed(4) || '0'} / ${dailyLimit}
            </span>
          </div>
          <div className="h-3 rounded-full bg-surface-800 overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-500',
                dailyPct >= 100 ? 'bg-red-500' : dailyPct >= 80 ? 'bg-amber-500' : 'bg-emerald-500',
              )}
              style={{ width: `${Math.min(dailyPct, 100)}%` }}
            />
          </div>
          <p className="text-xs text-surface-500 mt-2">{dailyPct.toFixed(1)}% used</p>
        </div>
      )}

      {/* Cost by Model */}
      {monthly && Object.keys(monthly.by_model || {}).length > 0 && (
        <div className="glass-panel p-5">
          <h3 className="font-medium mb-3 flex items-center gap-2">
            <DollarSignIcon size={16} className="text-emerald-400" />
            Cost by Model (This Month)
          </h3>
          <div className="space-y-2">
            {Object.entries(monthly.by_model)
              .sort((a, b) => b[1].cost_usd - a[1].cost_usd)
              .map(([model, data]) => (
                <div key={model} className="flex items-center justify-between py-2 px-3 rounded-xl bg-surface-800/50">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium">{model}</span>
                    <span className="chip text-[10px]">{data.calls} calls</span>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">${data.cost_usd.toFixed(6)}</p>
                    <p className="text-xs text-surface-500">{data.tokens.toLocaleString()} tokens</p>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Budget Configuration Modal */}
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setEditing(false)}>
          <div className="w-full max-w-lg glass-panel p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <DollarSignIcon size={18} className="text-emerald-400" />
              Configure Budget
            </h2>
            
            <div className="space-y-4">
              {/* Monthly Limit */}
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Monthly Spending Limit ($)</label>
                <input
                  type="number"
                  placeholder="Leave empty for unlimited"
                  value={form.monthly_limit_usd ?? ''}
                  onChange={(e) => setForm({ ...form, monthly_limit_usd: e.target.value ? Number(e.target.value) : null })}
                  className="input-field"
                  min="0"
                  step="0.01"
                />
              </div>

              {/* Daily Limit */}
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Daily Spending Limit ($)</label>
                <input
                  type="number"
                  placeholder="Leave empty for unlimited"
                  value={form.daily_limit_usd ?? ''}
                  onChange={(e) => setForm({ ...form, daily_limit_usd: e.target.value ? Number(e.target.value) : null })}
                  className="input-field"
                  min="0"
                  step="0.01"
                />
              </div>

              {/* Alert Threshold */}
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Alert at {form.alert_threshold_pct}% of budget</label>
                <input
                  type="range"
                  min="1"
                  max="100"
                  value={form.alert_threshold_pct}
                  onChange={(e) => setForm({ ...form, alert_threshold_pct: Number(e.target.value) })}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-surface-500 mt-1">
                  <span>1%</span>
                  <span>50%</span>
                  <span>100%</span>
                </div>
              </div>

              {/* Hard Limit Toggle */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-surface-800/50">
                <div>
                  <p className="font-medium text-sm">Hard Limit</p>
                  <p className="text-xs text-surface-500">Block API calls when budget exceeded</p>
                </div>
                <button
                  onClick={() => setForm({ ...form, hard_limit: !form.hard_limit })}
                  className={cn(
                    'w-12 h-6 rounded-full transition-all',
                    form.hard_limit ? 'bg-emerald-500' : 'bg-surface-700',
                  )}
                >
                  <div className={cn(
                    'w-5 h-5 rounded-full bg-white transition-transform',
                    form.hard_limit ? 'translate-x-6' : 'translate-x-0.5',
                  )} />
                </button>
              </div>

              {/* Alert Emails */}
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Alert Emails</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {form.alert_emails.map((email) => (
                    <span key={email} className="flex items-center gap-1 px-2 py-1 rounded-lg bg-primary-500/10 border border-primary-500/20 text-xs">
                      <MailIcon size={10} />
                      {email}
                      <button onClick={() => removeEmail(email)} className="text-surface-500 hover:text-red-400">×</button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    type="email"
                    placeholder="Add email..."
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addEmail()}
                    className="input-field flex-1"
                  />
                  <button onClick={addEmail} className="btn-secondary text-sm">Add</button>
                </div>
              </div>

              {/* Webhook URL */}
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Alert Webhook URL</label>
                <input
                  type="url"
                  placeholder="https://hooks.slack.com/..."
                  value={form.alert_webhook ?? ''}
                  onChange={(e) => setForm({ ...form, alert_webhook: e.target.value || null })}
                  className="input-field"
                />
                <p className="text-xs text-surface-500 mt-1">POST budget alerts to this URL</p>
              </div>
            </div>

            <div className="flex gap-3 pt-4">
              <button onClick={() => setEditing(false)} className="btn-secondary flex-1">Cancel</button>
              <button
                onClick={() => updateBudget(form)}
                disabled={isPending}
                className="btn-primary flex-1 flex items-center justify-center gap-2"
              >
                {isPending ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <><SaveIcon size={16} />Save Budget</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Quick Setup if no budget configured */}
      {!isLoading && !monthlyLimit && !dailyLimit && !editing && (
        <div className="glass-panel p-12 text-center">
          <DollarSignIcon className="w-12 h-12 text-surface-600 mx-auto mb-3" />
          <h3 className="text-lg font-medium text-surface-400">No budget configured</h3>
          <p className="text-sm text-surface-500 mt-1 mb-4">Set spending limits to avoid unexpected costs</p>
          <button onClick={startEdit} className="btn-primary">Configure Budget</button>
        </div>
      )}
    </div>
  )
}
