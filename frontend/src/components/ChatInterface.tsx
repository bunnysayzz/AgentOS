import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/utils/cn'
import { SendIcon, StopIcon, BotIcon, UserIcon, Trash2Icon, ChevronDownIcon, CopyIcon, CheckIcon } from '@/components/Icons'
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

// ─── Finished-markdown renderer ──────────────────────────────────────
// Tokens stream in as plain text for speed; once the stream ends, the full
// reply is formatted here with styled code blocks (copy button) and
// horizontally-scrollable tables.

function CodeBlock({ children }: { children?: React.ReactNode }) {
  const ref = useRef<HTMLPreElement>(null)
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    const text = ref.current?.innerText ?? ''
    try { await navigator.clipboard.writeText(text) } catch { return }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div className="group/code relative my-3 rounded-xl overflow-hidden border border-surface-700/40 bg-surface-950">
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface-900/80 border-b border-surface-700/30">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-red-500/60" />
          <span className="w-2 h-2 rounded-full bg-amber-500/60" />
          <span className="w-2 h-2 rounded-full bg-emerald-500/60" />
        </span>
        <button
          onClick={copy}
          title="Copy code"
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-surface-500 hover:text-surface-200 transition-colors"
        >
          {copied ? <CheckIcon size={11} className="text-emerald-400" /> : <CopyIcon size={11} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre ref={ref} className="overflow-x-auto p-3.5 text-[12.5px] leading-relaxed font-mono text-surface-100">
        {children}
      </pre>
    </div>
  )
}

function MarkdownView({ content }: { content: string }) {
  return (
    <div className="chat-md prose prose-invert prose-sm max-w-none prose-headings:text-surface-100 prose-p:text-surface-200 prose-li:text-surface-200 prose-strong:text-surface-100 prose-em:text-surface-200 prose-code:text-violet-300 prose-code:bg-surface-700/50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-[0.85em] prose-a:text-violet-400 prose-a:no-underline hover:prose-a:underline prose-li:marker:text-violet-400 prose-th:border-surface-700/60 prose-td:border-surface-700/40 prose-th:text-surface-200 prose-th:bg-surface-800/60 prose-td:text-surface-300 prose-table:text-sm prose-hr:border-surface-700/50 prose-blockquote:border-violet-500/40 prose-blockquote:text-surface-400">
      <Markdown
        components={{
          pre: ({ children }: { children?: React.ReactNode }) => <CodeBlock>{children}</CodeBlock>,
          table: (props: React.ComponentPropsWithoutRef<'table'>) => (
            <div className="overflow-x-auto my-2 rounded-lg border border-surface-700/30">
              <table {...props} className="w-full" />
            </div>
          ),
        }}
      >
        {content}
      </Markdown>
    </div>
  )
}

export default function ChatInterface({
  systemPrompt,
  defaultModel = 'gpt-4o-mini',
  workspaceId,
  showProviderSelector = true,
  height = '500px',
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
  // assistant bubble currently being generated: pendingId drives the typing
  // dots (no tokens yet) and then the live caret-while-streaming render. A ref
  // mirrors it so async stream handlers never read a stale closure.
  const [pendingId, setPendingId] = useState<string | null>(null)
  const pendingRef = useRef<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // If the chat unmounts mid-stream (tab switch), stop the request instead of
  // letting it mutate state that is no longer on screen.
  useEffect(() => () => controllerRef.current?.abort(), [])

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
    // During a stream, scroll instantly so the caret never lags behind;
    // use the smooth glide only when a new message lands.
    messagesEndRef.current?.scrollIntoView({ behavior: pendingId ? 'auto' : 'smooth', block: 'end' })
  }, [messages, pendingId])

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
      pendingRef.current = assistantId
      setPendingId(assistantId)
      setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '' }])

      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      const token = useAuthStore.getState().accessToken
      if (token) headers.Authorization = `Bearer ${token}`

      // Stop-generation support: aborting this controller cancels the fetch
      // (the reader throws) and we finalize with whatever streamed so far.
      const controller = new AbortController()
      controllerRef.current = controller

      let response: Response | null = null
      try {
        response = await fetch(`${API_BASE}/mcp/chat/stream`, {
          method: 'POST', headers, body: JSON.stringify(body), signal: controller.signal,
        })
      } catch { response = null }

      if (!response?.ok || !response.body) {
        if (!controller.signal.aborted) {
          // Non-stream fallback only when the server path failed for real —
          // never when the user pressed Stop while connecting.
          const fallback = await api.post('/mcp/chat/completions', { ...body, stream: false })
          const data = fallback.data
          const responseContent = data.choices?.[0]?.message?.content || '(empty response)'
          setMessages((prev) => [...prev, { id: `resp-${Date.now()}`, role: 'assistant', content: responseContent, created_at: new Date().toISOString() }])
        }
        setMessages((prev) => prev.filter((m) => m.id !== assistantId))
        pendingRef.current = null
        setPendingId(null)
        controllerRef.current = null
        return null
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let streamError: string | null = null
      let emitted = false

      const appendNow = (text: string) => {
        if (!text) return
        emitted = true
        setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: m.content + text } : m))
      }

      // Paint at most once per animation frame: incoming tokens accumulate in
      // a queue and flush together on the next rAF, so even very fast
      // providers render smoothly at 60fps instead of one React render per
      // token.
      let rafId: number | null = null
      let tokenQueue = ''
      const scheduleFlush = () => {
        if (rafId != null) return
        rafId = requestAnimationFrame(() => {
          rafId = null
          const chunk = tokenQueue
          tokenQueue = ''
          appendNow(chunk)
        })
      }
      const flushNow = () => {
        if (rafId != null) { cancelAnimationFrame(rafId); rafId = null }
        const chunk = tokenQueue
        tokenQueue = ''
        appendNow(chunk)
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
              if (payload.type === 'delta') {
                tokenQueue += payload.content
                scheduleFlush()
              } else if (payload.type === 'error') {
                streamError = payload.message
              }
            } catch { /* ignore malformed SSE lines */ }
          }
        }
      } catch (e: any) {
        if (controller.signal.aborted) {
          // User pressed Stop: keep whatever already streamed, no error.
        } else {
          streamError = e?.message || 'Stream interrupted'
        }
      }
      flushNow()

      if (controller.signal.aborted && !emitted) {
        // Stopped before the first token: drop the empty bubble entirely.
        setMessages((prev) => prev.filter((m) => m.id !== assistantId))
      }

      if (streamError) {
        setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: m.content || `Error: ${streamError}`, is_error: !m.content } : m))
        toast.error('Chat error', streamError)
      }
      pendingRef.current = null
      setPendingId(null)
      controllerRef.current = null
      return null
    },
    onSuccess: () => {
      pendingRef.current = null
      setPendingId(null)
    },
    onError: (err: any) => {
      const pid = pendingRef.current
      pendingRef.current = null
      setPendingId(null)
      const errorMsg = err.response?.data?.detail || err.message || 'Request failed'
      if (pid) {
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

  const stopGenerating = () => {
    controllerRef.current?.abort()
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
  const availableModels = getModelsForProvider(selectedProvider)
  const isResponding = pendingId !== null

  return (
    <div className={cn(
      'flex flex-col rounded-2xl overflow-hidden',
      'bg-gradient-to-b from-surface-900/90 to-surface-900/70',
      'border border-surface-700/30',
      'shadow-[0_8px_40px_-12px_rgba(0,0,0,0.6),0_0_0_1px_rgba(255,255,255,0.03)]'
    )} style={{ height }}>
      {/* Header — compact: identity left, routing controls + clear right */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 sm:px-5 py-2.5 border-b border-surface-700/20 bg-surface-800/20">
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/25 flex-shrink-0">
            <BotIcon size={15} className="text-white" />
          </div>
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-sm font-semibold text-surface-100 truncate">{title}</span>
            <span className="hidden md:flex items-center gap-1.5 text-[10px] font-medium text-surface-500">
              <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', isResponding ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400')} />
              {isResponding ? 'Responding…' : 'Ready'}
            </span>
          </div>
        </div>

        {hasProviders && (
          <div className="flex items-center gap-1.5">
            {/* Provider */}
            <div className="relative">
              <select
                value={selectedProvider}
                onChange={(e) => handleProviderChange(e.target.value)}
                aria-label="Provider"
                className="appearance-none h-7 max-w-[130px] bg-surface-900/70 border border-surface-700/30 hover:border-surface-600/50 rounded-lg pl-2.5 pr-6 text-xs font-medium text-surface-200 cursor-pointer transition-all focus:outline-none focus:border-violet-500/50 truncate"
              >
                {providerList.map((p) => (
                  <option key={p.provider} value={p.provider}>{getProviderLabel(p.provider)}</option>
                ))}
              </select>
              <ChevronDownIcon size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" />
            </div>
            <span className="text-surface-700 text-xs select-none">/</span>
            {/* Model */}
            {availableModels.length > 0 ? (
              <div className="relative max-w-[210px]">
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  aria-label="Model"
                  className="appearance-none h-7 w-full bg-surface-900/70 border border-surface-700/30 hover:border-surface-600/50 rounded-lg pl-2.5 pr-6 text-xs font-mono text-violet-300/90 cursor-pointer transition-all focus:outline-none focus:border-violet-500/50 truncate"
                >
                  {availableModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <ChevronDownIcon size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" />
              </div>
            ) : (
              <input
                type="text"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                placeholder={currentConfig?.default_model || 'model name'}
                aria-label="Model"
                className="w-[140px] h-7 bg-surface-900/70 border border-surface-700/30 hover:border-surface-600/50 rounded-lg px-2.5 text-xs font-mono text-violet-300/90 placeholder:text-surface-600 focus:outline-none focus:border-violet-500/50 transition-all truncate"
              />
            )}
          </div>
        )}
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
              {msg.role === 'user' || msg.is_error ? msg.content : msg.id === pendingId ? (
                // Pending bubble: typing dots until the first token, then the
                // raw text streams in with a caret. Markdown waits until the
                // stream finishes so every token renders instantly (GPT-style).
                msg.content === '' ? (
                  <div className="flex items-center gap-1.5 py-1" aria-label="Assistant is typing">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        className="w-1.5 h-1.5 rounded-full bg-violet-400/70 animate-bounce"
                        style={{ animationDelay: `${i * 150}ms` }}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="whitespace-pre-wrap break-words">
                    {msg.content}
                    <span className="inline-block w-[2px] h-[1em] ml-0.5 align-[-0.15em] bg-violet-400/80 animate-pulse" />
                  </div>
                )
              ) : (
                <MarkdownView content={msg.content} />
              )}
              {/* Copy button for finished bot messages */}
              {msg.role === 'assistant' && !msg.is_error && msg.content && msg.id !== 'welcome' && pendingId !== msg.id && (
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
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-surface-700/20 bg-surface-800/15 p-3 sm:p-4">
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
            onClick={isResponding ? stopGenerating : handleSend}
            disabled={!isResponding && (!input.trim() || sendMutation.isPending || !hasProviders)}
            title={isResponding ? 'Stop generating' : 'Send message'}
            aria-label={isResponding ? 'Stop generating' : 'Send message'}
            className={cn(
              'flex items-center justify-center w-11 h-11 rounded-xl transition-all duration-150 flex-shrink-0',
              isResponding
                ? 'bg-gradient-to-br from-red-500 to-rose-600 text-white shadow-lg shadow-red-500/25 hover:shadow-red-500/40 hover:scale-105 active:scale-95'
                : input.trim() && !sendMutation.isPending && hasProviders
                  ? 'bg-gradient-to-br from-violet-500 to-indigo-600 text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/35 hover:scale-105 active:scale-95'
                  : 'bg-surface-700/40 text-surface-500 cursor-not-allowed'
            )}
          >
            {isResponding ? <StopIcon size={15} /> : <SendIcon size={16} />}
          </button>
        </div>
      </div>
    </div>
  )
}
