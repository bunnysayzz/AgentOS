import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/utils/cn'
import { SendIcon, BotIcon, UserIcon, Trash2Icon, ChevronDownIcon, CopyIcon, CheckIcon } from '@/components/Icons'
import { toast } from '@/components/Toast'
import Markdown from 'react-markdown'

const API_BASE = import.meta.env.VITE_API_URL

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at?: string
  is_error?: boolean
}

interface ProviderConfig {
  provider: string
  default_model: string | null
  is_configured: boolean
  base_url: string | null
  created_at: string
}

interface ChatInterfaceProps {
  systemPrompt?: string
  defaultModel?: string
  workspaceId?: string
  showProviderSelector?: boolean
  height?: string
  title?: string
  placeholder?: string
  fullHeight?: boolean
}

// Provider → available models mapping
const PROVIDER_MODELS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1-preview', 'o1-mini', 'gpt-3.5-turbo'],
  anthropic: ['claude-3-5-sonnet', 'claude-3-5-haiku-20241022', 'claude-3-opus', 'claude-3-haiku'],
  google: ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.5-pro-preview-05-06'],
  groq: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
  deepseek: ['deepseek-chat', 'deepseek-reasoner'],
  agentrouter: ['deepseek/deepseek-v4-flash', 'deepseek/deepseek-v4-chat'],
  mistral: ['open-mistral-nemo', 'mistral-large-latest', 'mistral-small-latest'],
  openrouter: ['meta-llama/llama-3.3-70b-instruct:free', 'openai/gpt-4o-mini', 'anthropic/claude-3.5-sonnet'],
  cerebras: ['llama-3.3-70b', 'llama-3.1-8b'],
  huggingface: ['meta-llama/Llama-3.3-70B-Instruct', 'meta-llama/Llama-3.1-8B-Instruct'],
  nvidia_nim: ['meta/llama-3.1-8b-instruct', 'meta/llama-3.3-70b-instruct'],
  togetherai: ['meta-llama/Llama-3.3-70B-Instruct-Turbo', 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo'],
  fireworks: ['accounts/fireworks/models/llama-v3p3-70b-instruct'],
  deepinfra: ['meta-llama/Meta-Llama-3.1-70B-Instruct'],
  ollama: ['llama3.2', 'llama3.1', 'mistral', 'codellama'],
  xai: ['grok-2-1212', 'grok-2-mini'],
  novita: ['meta-llama/llama-3.3-70b-instruct'],
  perplexity: ['sonar-pro', 'sonar-small-online'],
  sambanova: ['Meta-Llama-3.3-70B-Instruct'],
  hyperbolic: ['meta-llama/Meta-Llama-3.1-70B-Instruct'],
  github_models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo'],
  moonshotai: ['moonshot-v1-128k'],
  upstage: ['solar-pro-2-preview'],
  nebius: ['meta-llama/Meta-Llama-3.1-70B-Instruct'],
  llmapi: ['gpt-4o', 'gpt-4o-mini'],
}

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google Gemini',
  groq: 'Groq', mistral: 'Mistral', deepseek: 'DeepSeek',
  openrouter: 'OpenRouter', cerebras: 'Cerebras', huggingface: 'HuggingFace',
  nvidia_nim: 'NVIDIA NIM', togetherai: 'Together AI', ollama: 'Ollama',
  agentrouter: 'AgentRouter', xai: 'xAI', fireworks: 'Fireworks',
  deepinfra: 'DeepInfra', novita: 'Novita AI', perplexity: 'Perplexity',
  moonshotai: 'Moonshot AI', upstage: 'Upstage', nebius: 'Nebius',
  github_models: 'GitHub Models', llmapi: 'LLM API', hyperbolic: 'Hyperbolic',
  sambanova: 'SambaNova',
}

function getProviderLabel(provider: string): string {
  return PROVIDER_LABELS[provider] || provider.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

function getModelsForProvider(provider: string): string[] {
  return PROVIDER_MODELS[provider] || []
}

export default function ChatInterface({
  systemPrompt,
  defaultModel = 'gpt-4o-mini',
  workspaceId,
  showProviderSelector = true,
  height = '500px',
  fullHeight = false,
  title = 'Chat',
  placeholder = 'Type a message...',
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: systemPrompt
        ? `Ready! I'll use the system prompt you configured. Ask me anything.`
        : `Hello! I'm an AI assistant. Send me a message and I'll respond using the configured model.`,
    },
  ])
  const [input, setInput] = useState('')
  const [selectedProvider, setSelectedProvider] = useState<string>('')
  const [selectedModel, setSelectedModel] = useState(defaultModel)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [streaming, setStreaming] = useState(false)
  const placeholderRef = useRef<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const { data: providers } = useQuery({
    queryKey: ['provider-configs'],
    queryFn: () => api.get('/mcp/providers').then((r) => r.data),
    enabled: showProviderSelector,
  })

  const providerList: ProviderConfig[] = Array.isArray(providers) ? providers.filter((p) => p.is_configured) : []

  useEffect(() => {
    if (providerList.length > 0 && !selectedProvider) {
      const first = providerList[0]
      setSelectedProvider(first.provider)
      if (first.default_model) setSelectedModel(first.default_model)
      else {
        const models = getModelsForProvider(first.provider)
        if (models.length > 0) setSelectedModel(models[0])
      }
    }
  }, [providerList, selectedProvider])

  const handleProviderChange = (provider: string) => {
    setSelectedProvider(provider)
    const config = providerList.find((p) => p.provider === provider)
    if (config?.default_model) {
      setSelectedModel(config.default_model)
    } else {
      const models = getModelsForProvider(provider)
      if (models.length > 0) setSelectedModel(models[0])
      else setSelectedModel('')
    }
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      const chatMessages: any[] = []
      if (systemPrompt) chatMessages.push({ role: 'system', content: systemPrompt })
      for (const msg of messages) {
        if (msg.id !== 'welcome' && !msg.is_error) {
          chatMessages.push({ role: msg.role, content: msg.content })
        }
      }
      chatMessages.push({ role: 'user', content })

      const body: any = {
        model: selectedModel,
        messages: chatMessages,
        temperature: 0.7,
        max_tokens: 2048,
        stream: true,
        ...(workspaceId ? { workspace_id: workspaceId } : {}),
      }

      const assistantId = `resp-${Date.now()}`
      placeholderRef.current = assistantId
      setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '' }])
      setStreaming(false)

      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      const token = useAuthStore.getState().accessToken
      if (token) headers.Authorization = `Bearer ${token}`

      let response: Response | null = null
      try {
        response = await fetch(`${API_BASE}/mcp/chat/stream`, {
          method: 'POST', headers, body: JSON.stringify(body),
        })
      } catch { response = null }

      if (!response?.ok || !response.body) {
        setMessages((prev) => prev.filter((m) => m.id !== assistantId))
        placeholderRef.current = null
        const fallback = await api.post('/mcp/chat/completions', { ...body, stream: false })
        const data = fallback.data
        const responseContent = data.choices?.[0]?.message?.content || '(empty response)'
        setMessages((prev) => [...prev, { id: `resp-${Date.now()}`, role: 'assistant', content: responseContent, created_at: new Date().toISOString() }])
        return null
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let streamError: string | null = null

      const appendToken = (tokenText: string) => {
        setStreaming(true)
        setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: m.content + tokenText } : m))
      }

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const frames = buffer.split('\n\n')
          buffer = frames.pop() ?? ''
          for (const frame of frames) {
            const line = frame.split('\n').find((l) => l.startsWith('data:'))
            if (!line) continue
            const payloadStr = line.slice(5).trim()
            if (!payloadStr) continue
            try {
              const payload = JSON.parse(payloadStr)
              if (payload.type === 'delta') appendToken(payload.content)
              else if (payload.type === 'error') streamError = payload.message
            } catch {}
          }
        }
      } catch (e: any) { streamError = e?.message || 'Stream interrupted' }

      placeholderRef.current = null
      if (streamError) {
        setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: m.content || `Error: ${streamError}`, is_error: !m.content } : m))
        toast.error('Chat error', streamError)
      }
      return null
    },
    onSuccess: () => setStreaming(false),
    onError: (err: any) => {
      setStreaming(false)
      const errorMsg = err.response?.data?.detail || err.message || 'Request failed'
      const pid = placeholderRef.current
      if (pid) {
        placeholderRef.current = null
        setMessages((prev) => prev.map((m) => m.id === pid ? { ...m, content: m.content || `Error: ${errorMsg}`, is_error: !m.content } : m))
      } else {
        setMessages((prev) => [...prev, { id: `err-${Date.now()}`, role: 'assistant', content: `Error: ${errorMsg}`, is_error: true }])
      }
      toast.error('Chat error', errorMsg)
    },
  })

  const handleSend = () => {
    const content = input.trim()
    if (!content || sendMutation.isPending) return
    setMessages((prev) => [...prev, { id: `user-${Date.now()}`, role: 'user', content }])
    setInput('')
    sendMutation.mutate(content)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const clearChat = () => {
    setMessages([{ id: 'welcome', role: 'assistant', content: systemPrompt ? `Chat cleared! I'll still use your system prompt.` : `Chat cleared! Send a new message to start.` }])
  }

  const handleCopy = (msgId: string, content: string) => {
    navigator.clipboard.writeText(content)
    setCopiedId(msgId)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const hasProviders = providerList.length > 0
  const currentConfig = providerList.find((p) => p.provider === selectedProvider)
  const displayProvider = currentConfig ? getProviderLabel(selectedProvider) : ''
  const displayModel = selectedModel || currentConfig?.default_model || 'auto'
  const availableModels = getModelsForProvider(selectedProvider)

  // Check if the last message is an empty assistant bubble (streaming started)
  const lastMsg = messages[messages.length - 1]
  const hasPendingBubble = lastMsg?.role === 'assistant' && lastMsg?.content === '' && lastMsg?.id.startsWith('resp-')

  return (
    <div className={cn(
      'flex flex-col rounded-2xl overflow-hidden',
      'bg-gradient-to-b from-surface-900/90 to-surface-900/70',
      'border border-surface-700/30',
      'shadow-[0_8px_40px_-12px_rgba(0,0,0,0.6),0_0_0_1px_rgba(255,255,255,0.03)]',
      !fullHeight && 'max-h-[700px]'
    )} style={{ height }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 sm:px-5 py-3 border-b border-surface-700/20 bg-surface-800/20">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/25 flex-shrink-0">
            <BotIcon size={16} className="text-white" />
          </div>
          <div className="min-w-0">
            <span className="text-sm font-semibold text-surface-100">{title}</span>
            {hasProviders && (
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-[11px] text-surface-400 truncate">{displayProvider}</span>
                <span className="text-[11px] text-surface-600">/</span>
                <span className="text-[11px] text-violet-400/80 font-mono truncate">{displayModel}</span>
              </div>
            )}
          </div>
        </div>
        <button onClick={clearChat} className="icon-btn" title="Clear chat">
          <Trash2Icon size={14} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-5 py-4 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className={cn('flex gap-3', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
            {msg.role !== 'user' && (
              <div className={cn(
                'w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5',
                msg.is_error ? 'bg-red-500/10 border border-red-500/20' : 'bg-gradient-to-br from-violet-500/15 to-indigo-500/15 border border-violet-500/10'
              )}>
                {msg.is_error ? <span className="text-red-400 text-xs font-bold">!</span> : <BotIcon size={14} className="text-violet-400" />}
              </div>
            )}
            <div className={cn(
              'max-w-[85%] sm:max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed group/msg relative',
              msg.role === 'user'
                ? 'bg-gradient-to-br from-violet-600/25 to-indigo-600/20 border border-violet-500/15 text-surface-100 rounded-br-md whitespace-pre-wrap'
                : msg.is_error
                ? 'bg-red-500/5 border border-red-500/10 text-red-300 rounded-bl-md whitespace-pre-wrap'
                : 'bg-surface-800/50 border border-surface-700/20 text-surface-200 rounded-bl-md'
            )}>
              {msg.role === 'user' || msg.is_error ? msg.content : (
                <div className="prose prose-invert prose-sm max-w-none prose-headings:text-surface-100 prose-p:text-surface-200 prose-li:text-surface-200 prose-strong:text-surface-100 prose-code:text-violet-300 prose-code:bg-surface-700/50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-pre:bg-surface-950 prose-pre:border prose-pre:border-surface-700/50 prose-a:text-violet-400 prose-a:no-underline hover:prose-a:underline prose-li:marker:text-violet-400">
                  <Markdown>{msg.content}</Markdown>
                </div>
              )}
              {/* Copy button for bot messages with content */}
              {msg.role === 'assistant' && !msg.is_error && msg.content && msg.id !== 'welcome' && (
                <button
                  onClick={() => handleCopy(msg.id, msg.content)}
                  className="absolute top-2 right-2 opacity-0 group-hover/msg:opacity-100 icon-btn !w-7 !h-7"
                  title="Copy message"
                >
                  {copiedId === msg.id ? <CheckIcon size={13} className="text-emerald-400" /> : <CopyIcon size={13} />}
                </button>
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-surface-600 to-surface-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                <UserIcon size={14} className="text-surface-300" />
              </div>
            )}
          </div>
        ))}
        {/* Loading indicator - only show if NO pending bubble exists yet */}
        {sendMutation.isPending && !streaming && !hasPendingBubble && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-500/15 to-indigo-500/15 border border-violet-500/10 flex items-center justify-center">
              <BotIcon size={14} className="text-violet-400" />
            </div>
            <div className="bg-surface-800/50 border border-surface-700/20 rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex gap-1.5">
                <div className="w-1.5 h-1.5 bg-violet-400/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-1.5 h-1.5 bg-violet-400/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-1.5 h-1.5 bg-violet-400/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-surface-700/20 bg-surface-800/15 p-3 sm:p-4">
        {/* Provider + Model row */}
        {hasProviders && (
          <div className="flex gap-2 mb-3">
            <div className="flex-1 min-w-0">
              <label className="text-[10px] text-surface-500 mb-1 block font-medium uppercase tracking-wider">Provider</label>
              <div className="relative">
                <select
                  value={selectedProvider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="w-full appearance-none bg-surface-800/50 border border-surface-700/30 rounded-xl text-xs py-2.5 pl-3 pr-8 text-surface-200 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition-all cursor-pointer truncate hover:border-surface-600/50"
                  aria-label="Provider"
                >
                  {providerList.map((p) => (
                    <option key={p.provider} value={p.provider}>{getProviderLabel(p.provider)}</option>
                  ))}
                </select>
                <ChevronDownIcon size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" />
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <label className="text-[10px] text-surface-500 mb-1 block font-medium uppercase tracking-wider">Model</label>
              {availableModels.length > 0 ? (
                <div className="relative">
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="w-full appearance-none bg-surface-800/50 border border-surface-700/30 rounded-xl text-xs py-2.5 pl-3 pr-8 text-surface-200 font-mono focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition-all cursor-pointer truncate hover:border-surface-600/50"
                    aria-label="Model"
                  >
                    {availableModels.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                  <ChevronDownIcon size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" />
                </div>
              ) : (
                <input
                  type="text"
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  placeholder={currentConfig?.default_model || 'model name'}
                  className="w-full bg-surface-800/50 border border-surface-700/30 rounded-xl text-xs py-2.5 px-3 text-surface-200 font-mono placeholder:text-surface-600 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition-all hover:border-surface-600/50"
                />
              )}
            </div>
          </div>
        )}

        {/* Message input */}
        <div className="flex gap-2.5 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={hasProviders ? placeholder : 'Configure a provider first...'}
            className="flex-1 bg-surface-800/50 border border-surface-700/30 rounded-xl text-sm px-4 py-3 pr-12 resize-none min-h-[44px] max-h-[120px] text-surface-100 placeholder:text-surface-600 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition-all hover:border-surface-600/50"
            rows={1}
            disabled={!hasProviders}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || sendMutation.isPending || !hasProviders}
            className={cn(
              'flex items-center justify-center w-11 h-11 rounded-xl transition-all duration-150 flex-shrink-0',
              input.trim() && !sendMutation.isPending && hasProviders
                ? 'bg-gradient-to-br from-violet-500 to-indigo-600 text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/35 hover:scale-105 active:scale-95'
                : 'bg-surface-700/40 text-surface-500 cursor-not-allowed'
            )}
          >
            {sendMutation.isPending ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <SendIcon size={16} />}
          </button>
        </div>
      </div>
    </div>
  )
}
