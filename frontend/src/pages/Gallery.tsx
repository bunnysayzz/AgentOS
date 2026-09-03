import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BotIcon, GlobeIcon, LogInIcon,
  RocketIcon, SearchIcon, XIcon,
} from '@/components/Icons'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { toast } from '@/components/Toast'

interface GalleryAgent {
  id: string
  name: string
  description?: string | null
  system_prompt?: string | null
  model_provider: string
  model_name: string
  temperature?: number
  max_tokens?: number
  status: string
  author_username: string
  workspace_name: string
  tool_count?: number
  clone_count?: number
  tags?: string[]
  featured?: boolean
  published_at?: string | null
  created_at?: string
}

export default function Gallery() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const [detail, setDetail] = useState<GalleryAgent | null>(null)
  const [cloneError, setCloneError] = useState('')
  const [search, setSearch] = useState('')
  const [selectedTag, setSelectedTag] = useState<string | null>(null)

  const { data: agents, isLoading, isError } = useQuery({
    queryKey: ['gallery'],
    queryFn: () => api.get('/gallery/').then((r) => r.data),
  })

  const { mutate: clone, isPending: cloning } = useMutation({
    mutationFn: (id: string) => api.post(`/gallery/${id}/clone`).then((r) => r.data),
    onSuccess: (agent: any) => {
      qc.invalidateQueries({ queryKey: ['agents'] })
      qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
      toast.success('Agent cloned', `"${agent.name}" was added to your workspace as a draft.`)
      // Land inside the freshly cloned agent, ready to run or edit.
      navigate(`/agents?open=${encodeURIComponent(agent.id)}`)
    },
    onError: (err: any) => {
      setCloneError(err?.response?.data?.detail || 'Failed to clone this agent.')
    },
  })

  const list: GalleryAgent[] = Array.isArray(agents) ? agents : []
  const allTags = Array.from(new Set(list.flatMap((a) => a.tags || [])))
  const filteredList = list.filter((a) => {
    const matchesSearch = !search ||
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      (a.description || '').toLowerCase().includes(search.toLowerCase())
    const matchesTag = !selectedTag || (a.tags || []).includes(selectedTag)
    return matchesSearch && matchesTag
  })
  const featured = filteredList.filter((a) => a.featured)
  const regular = filteredList.filter((a) => !a.featured)

  const handleUse = (agent: GalleryAgent) => {
    setCloneError('')
    if (!isAuthenticated) {
      navigate('/login?redirect=/gallery')
      return
    }
    clone(agent.id)
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-500/10 border border-primary-500/25 text-primary-300 text-xs font-medium mb-3">
          <GlobeIcon size={13} />
          Community agent gallery
        </div>
        <h1 className="text-2xl font-bold">Gallery</h1>
        <p className="text-surface-400 text-sm mt-1">
          Browse agents built by the community, inspect their system prompts, and clone
          any of them into your workspace with one click.
        </p>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <input
            type="text"
            placeholder="Search agents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-field pl-10"
          />
          <SearchIcon size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-surface-500" />
        </div>
        {allTags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedTag(null)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                !selectedTag ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30' : 'bg-surface-800/50 text-surface-400 border border-surface-700/30 hover:bg-surface-800'
              }`}
            >
              All
            </button>
            {allTags.slice(0, 6).map((tag) => (
              <button
                key={tag}
                onClick={() => setSelectedTag(selectedTag === tag ? null : tag)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  selectedTag === tag ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30' : 'bg-surface-800/50 text-surface-400 border border-surface-700/30 hover:bg-surface-800'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Grid */}
      {isError ? (
        <div className="rounded-2xl bg-surface-800/40 border border-surface-700/25 p-10 text-center">
          <p className="text-surface-400 text-sm">Couldn't load the gallery. Please try again.</p>
        </div>
      ) : isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-2xl bg-surface-800/40 border border-surface-700/25 p-5 animate-pulse">
              <div className="h-10 w-10 bg-surface-700/50 rounded-xl mb-4" />
              <div className="h-4 w-2/3 bg-surface-700/50 rounded mb-2" />
              <div className="h-3 w-full bg-surface-700/50 rounded mb-1" />
              <div className="h-3 w-4/5 bg-surface-700/50 rounded" />
            </div>
          ))}
        </div>
      ) : list.length === 0 ? (
        <div className="rounded-2xl bg-surface-800/40 border border-surface-700/25 p-14 text-center">
          <BotIcon className="w-12 h-12 text-surface-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-surface-300">No agents published yet</h3>
          <p className="text-sm text-surface-500 mt-1 max-w-sm mx-auto">
            The gallery grows from the community. Publish an active agent from the Agents page and it will appear here.
          </p>
          {isAuthenticated && (
            <Link to="/agents" className="inline-flex items-center gap-2 mt-5 px-4 py-2 rounded-xl text-sm font-semibold text-white" style={{ background: 'linear-gradient(120deg, #7c3aed, #a78bfa)' }}>
              <RocketIcon size={15} />
              Publish your first agent
            </Link>
          )}
        </div>
      ) : (
        <div>
          {featured.length > 0 && (
            <div className="mb-8">
              <h3 className="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-primary-400" />
                Featured
              </h3>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {featured.map((agent) => (
                  <div
                    key={agent.id}
                    onClick={() => { setCloneError(''); setDetail(agent) }}
                    className="group relative rounded-2xl bg-gradient-to-b from-surface-800/60 to-surface-800/30 border border-surface-700/25 p-5 cursor-pointer hover:border-surface-600/40 transition-all duration-200 flex flex-col"
                  >
                    <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-500 to-indigo-500 rounded-t-2xl" />
                    <div className="flex items-start justify-between mb-3">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500/15 to-indigo-500/15 border border-violet-500/10 flex items-center justify-center">
                        <BotIcon size={18} className="text-violet-400" />
                      </div>
                      <div className="flex items-center gap-2">
                        {agent.clone_count != null && agent.clone_count > 0 && (
                          <span className="text-[10px] bg-violet-500/10 text-violet-400 border border-violet-500/20 px-2 py-0.5 rounded-full">
                            {agent.clone_count} clones
                          </span>
                        )}
                        <span className="text-[10px] text-surface-500 bg-surface-800/60 border border-surface-700/30 px-2 py-0.5 rounded-full">{agent.model_name}</span>
                      </div>
                    </div>
                    <h3 className="font-medium text-surface-100 group-hover:text-violet-300 transition-colors">
                      {agent.name}
                    </h3>
                    <p className="text-sm text-surface-500 mt-1 mb-4 line-clamp-2 flex-1">
                      {agent.description || 'No description'}
                    </p>
                    {agent.tags && agent.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mb-3">
                        {agent.tags.slice(0, 3).map((tag) => (
                          <span key={tag} className="px-2 py-0.5 rounded text-[10px] bg-surface-800/60 text-surface-400 border border-surface-700/25">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-surface-600">
                        @{agent.author_username} <span className="text-surface-700">·</span> {agent.workspace_name}
                      </p>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleUse(agent) }}
                        disabled={cloning}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition-all hover:opacity-90"
                        style={{ background: 'linear-gradient(120deg, #7c3aed, #a78bfa)' }}
                      >
                        <RocketIcon size={12} />
                        Use this agent
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Regular Agents */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {regular.map((agent) => (
              <div
                key={agent.id}
                onClick={() => { setCloneError(''); setDetail(agent) }}
                className="group rounded-2xl bg-gradient-to-b from-surface-800/60 to-surface-800/30 border border-surface-700/25 p-5 cursor-pointer hover:border-surface-600/40 transition-all duration-200 flex flex-col"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/15 to-emerald-500/10 border border-emerald-500/10 flex items-center justify-center">
                    <BotIcon size={18} className="text-emerald-400" />
                  </div>
                  <div className="flex items-center gap-2">
                    {agent.clone_count != null && agent.clone_count > 0 && (
                      <span className="text-[10px] text-surface-500 bg-surface-800/60 border border-surface-700/30 px-2 py-0.5 rounded-full">
                        {agent.clone_count} clones
                      </span>
                    )}
                    <span className="text-[10px] text-surface-500 bg-surface-800/60 border border-surface-700/30 px-2 py-0.5 rounded-full">{agent.model_name}</span>
                  </div>
                </div>
                <h3 className="font-medium text-surface-100 group-hover:text-violet-300 transition-colors">
                  {agent.name}
                </h3>
                <p className="text-sm text-surface-500 mt-1 mb-4 line-clamp-2 flex-1">
                  {agent.description || 'No description'}
                </p>
                {agent.tags && agent.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {agent.tags.slice(0, 3).map((tag) => (
                      <span key={tag} className="px-2 py-0.5 rounded text-[10px] bg-surface-800/60 text-surface-400 border border-surface-700/25">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <p className="text-xs text-surface-600">
                    @{agent.author_username} <span className="text-surface-700">·</span> {agent.workspace_name}
                  </p>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleUse(agent) }}
                    disabled={cloning}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition-all hover:opacity-90"
                    style={{ background: 'linear-gradient(120deg, #7c3aed, #a78bfa)' }}
                  >
                    <RocketIcon size={12} />
                    Use this agent
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Detail modal */}
      {detail && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={() => setDetail(null)}
        >
          <div
            className="w-full max-w-lg rounded-2xl bg-surface-900/95 backdrop-blur-xl border border-surface-700/30 p-6 max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-1">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/15 to-emerald-500/10 border border-emerald-500/10 flex items-center justify-center">
                  <BotIcon size={18} className="text-emerald-400" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold">{detail.name}</h2>
                  <p className="text-xs text-surface-500">
                    @{detail.author_username} · {detail.workspace_name} · {detail.model_name}
                  </p>
                </div>
              </div>
              <button onClick={() => setDetail(null)} className="p-1.5 rounded-lg text-surface-500 hover:text-surface-300 hover:bg-surface-800 transition-all">
                <XIcon size={16} />
              </button>
            </div>

            {detail.description && (
              <p className="text-sm text-surface-400 mt-3">{detail.description}</p>
            )}

            <div className="mt-4">
              <p className="text-xs font-medium text-surface-500 uppercase tracking-wider mb-1.5">System prompt</p>
              <pre className="text-xs text-surface-300 bg-surface-900/50 border border-surface-700/20 rounded-xl p-3 whitespace-pre-wrap break-words max-h-56 overflow-y-auto font-mono">
                {detail.system_prompt || 'No system prompt'}
              </pre>
            </div>

            {cloneError && (
              <div className="mt-4 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {cloneError}
              </div>
            )}

            <div className="mt-5 flex items-center gap-3">
              {isAuthenticated ? (
                <button
                  onClick={() => clone(detail.id)}
                  disabled={cloning}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold text-white transition-all"
                  style={{ background: 'linear-gradient(120deg, #7c3aed, #a78bfa)' }}
                >
                  {cloning ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <RocketIcon size={15} />
                  )}
                  Clone into my workspace
                </button>
              ) : (
                <button
                  onClick={() => handleUse(detail)}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold text-white transition-all"
                  style={{ background: 'linear-gradient(120deg, #7c3aed, #a78bfa)' }}
                >
                  <LogInIcon size={15} />
                  Sign in to clone this agent
                </button>
              )}
              <button onClick={() => setDetail(null)} className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium bg-surface-700/30 border border-surface-600/20 text-surface-300 hover:bg-surface-700/50 transition-all">
                Cancel
              </button>
            </div>
            {isAuthenticated && (
              <p className="text-[11px] text-surface-600 mt-3 text-center">
                Secrets and tool bindings stay in the original workspace. The clone arrives as a draft you review first.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
