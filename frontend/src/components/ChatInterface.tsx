import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/utils/cn'
import { SendIcon, BotIcon, UserIcon, Trash2Icon, ChevronDownIcon } from '@/components/Icons'
import Markdown from 'react-markdown'
import { toast } from '@/components/Toast'

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

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google Gemini',
  groq: 'Groq', mistral: 'Mistral', deepseek: 'DeepSeek',
  openrouter: 'OpenRouter', cerebras: 'Cerebras', huggingface: 'HuggingFace',
  nvidia_nim: 'NVIDIA NIM', togetherai: 'Together AI', ollama: 'Ollama',
  agentrouter: 'AgentRouter', xai: 'xAI', fireworks: 'Fireworks',
  deepinfra: 'DeepInfra', novita: 'Novita AI', perplexity: 'Perplexity',
  moonshotai: 'Moonshot AI', upstage: 'Upstage', nebius: 'Nebius',
  github_models: 'GitHub Models', llmapi: 'LLM API', hyperbolic: 'Hyperbolic',
  sambanova: 'SambaNova', volcengine: 'Volcengine', zhipu: 'Zhipu AI',
  minimax: 'MiniMax', bailian: 'Bailian', deepseek_official: 'DeepSeek',
  cerebras_cloud: 'Cerebras Cloud', amazon_bedrock: 'Amazon Bedrock',
  azure: 'Azure OpenAI', vercel_ai_gateway: 'Vercel AI Gateway',
  kunlun: 'Kunlun', siliconflow: 'SiliconFlow', inflection: 'Inflection',
  alibaba: 'Alibaba Cloud', tencent: 'Tencent Cloud', baidu: 'Baidu AI',
  sensenova: 'SenseTime', iflytek: 'iFlyTek', taichu: 'Taichu',
  skywork: 'Skywork', baichuan: 'Baichuan', yi: 'Yi AI',
  united: 'United AI', stardust: 'Stardust', chutes: 'Chutes AI',
  nsummit: 'NSummit', aihorde: 'AI Horde', blackbox: 'Blackbox AI',
  apifreellm: 'API Free LLM', lepton: 'Lepton AI', cloudflare: 'Cloudflare',
  dashscope: 'DashScope', volcark: 'Volcark', proxiflow: 'ProxiFlow',
  astra: 'Astra', safedeploy: 'SafeDeploy', aiml: 'AIML',
  askalta: 'AskAlta', lobehub: 'LobeHub', zentia: 'Zentia',
  calebf: 'CalebF', inflection_3: 'Inflection 3', minimax_pro: 'MiniMax Pro',
  qwen: 'Qwen', chatglm: 'ChatGLM', codegeex: 'CodeGeeX',
  wolfram: 'Wolfram Alpha', phospho: 'Phospho', portkey: 'Portkey',
  unbound: 'Unbound', vero: 'Vero', vercel: 'Vercel',
  vllm: 'vLLM', xinference: 'Xinference', skyrogue: 'SkyRogue',
  skybridge: 'SkyBridge', kai: 'KAI', gitee: 'Gitee AI',
  volcengine_maas: 'Volcengine MaaS', zeabur: 'Zeabur',
  zai: 'Z.AI', aws_bedrock: 'AWS Bedrock', zhipuai: 'ZhipuAI',
  baichuan2: 'Baichuan 2', xinghuo: 'Xinghuo', streamer: 'Streamer',
  edge: 'Edge AI', openchat: 'OpenChat', anyscale: 'Anyscale',
  deepinfra_v2: 'DeepInfra V2', zeta: 'Zeta', dynamo: 'Dynamo',
  crow: 'Crow AI', openrouter_mini: 'OpenRouter Mini', vercel_ai: 'Vercel AI',
  llama_cpp: 'llama.cpp', ollama2: 'Ollama 2', together: 'Together',
  fireworks_v2: 'Fireworks V2', groq_v2: 'Groq V2', deepseek_v2: 'DeepSeek V2',
  nvidia_nim_v2: 'NVIDIA NIM V2', mistral_v2: 'Mistral V2',
}

function getProviderLabel(provider: string): string {
  return PROVIDER_LABELS[provider] || provider.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
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

  const { data: providers } = useQuery({
    queryKey: ['provider-configs'],
    queryFn: () => api.get('/mcp/providers').then((r) => r.data),
    enabled: showProviderSelector,
  })

  const providerList: ProviderConfig[] = Array.isArray(providers) ? providers.filter((p) => p.is_configured) : []

  // Auto-select first provider and sync model
  useEffect(() => {
    if (providerList.length > 0 && !selectedProvider) {
      const first = providerList[0]
      setSelectedProvider(first.provider)
      if (first.default_model) {
        setSelectedModel(first.default_model)
      }
    }
  }, [providerList, selectedProvider])

  // When provider changes, auto-fill model from provider's default
  const handleProviderChange = (provider: string) => {
    setSelectedProvider(provider)
    const config = providerList.find((p) => p.provider === provider)
    if (config?.default_model) {
      setSelectedModel(config.default_model)
    }
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      const chatMessages: any[] = []
      if (systemPrompt) {
        chatMessages.push({ role: 'system', content: systemPrompt })
      }
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
          method: 'POST',
          headers,
          body: JSON.stringify(body),
        })
      } catch {
        response = null
      }

      if (!response?.ok || !response.body) {
        setMessages((prev) => prev.filter((m) => m.id !== assistantId))
        placeholderRef.current = null
        const fallback = await api.post('/mcp/chat/completions', { ...body, stream: false })
        const data = fallback.data
        const responseContent = data.choices?.[0]?.message?.content || '(empty response)'
        setMessages((prev) => [
          ...prev,
          {
            id: `resp-${Date.now()}`,
            role: 'assistant',
            content: responseContent,
            created_at: new Date().toISOString(),
          },
        ])
        if (data.usage) {
          const { prompt_tokens, completion_tokens, total_tokens } = data.usage
          console.log(`[${data.provider}/${data.model}] Tokens: ${total_tokens} (${prompt_tokens}in + ${completion_tokens}out)`)
        }
        return null
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let streamError: string | null = null

      const appendToken = (tokenText: string) => {
        setStreaming(true)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + tokenText } : m
          )
        )
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
                appendToken(payload.content)
              } else if (payload.type === 'done') {
                const usage = payload.usage || {}
                const total = usage.total_tokens ?? (usage.prompt_tokens || 0) + (usage.completion_tokens || 0)
                console.log(`[${payload.provider}/${payload.model}] Tokens: ${total} · $${payload.cost_usd ?? 0}`)
              } else if (payload.type === 'error') {
                streamError = payload.message
              }
            } catch {
              // malformed frame — ignore
            }
          }
        }
      } catch (e: any) {
        streamError = e?.message || 'Stream interrupted'
      }

      placeholderRef.current = null
      if (streamError) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: m.content || `Error: ${streamError}`, is_error: !m.content }
              : m
          )
        )
        toast.error('Chat error', streamError)
      }
      return null
    },
    onSuccess: () => {
      setStreaming(false)
    },
    onError: (err: any) => {
      setStreaming(false)
      const errorMsg = err.response?.data?.detail || err.message || 'Request failed'
      const pid = placeholderRef.current
      if (pid) {
        placeholderRef.current = null
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pid
              ? { ...m, content: m.content || `Error: ${errorMsg}`, is_error: !m.content }
              : m
          )
        )
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: 'assistant',
            content: `Error: ${errorMsg}`,
            is_error: true,
          },
        ])
      }
      toast.error('Chat error', errorMsg)
    },
  })

  const handleSend = () => {
    const content = input.trim()
    if (!content || sendMutation.isPending) return

    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: 'user', content },
    ])
    setInput('')
    sendMutation.mutate(content)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const clearChat = () => {
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: systemPrompt
          ? `Chat cleared! I'll still use your system prompt.`
          : `Chat cleared! Send a new message to start.`,
      },
    ])
  }

  const hasProviders = providerList.length > 0
  const currentConfig = providerList.find((p) => p.provider === selectedProvider)
  const displayProvider = currentConfig ? getProviderLabel(selectedProvider) : ''
  const displayModel = selectedModel || currentConfig?.default_model || 'auto'

  return (
    <div className={cn('flex flex-col bg-surface-900/80 backdrop-blur-xl rounded-2xl border border-surface-700/40 overflow-hidden shadow-2xl shadow-black/20', !fullHeight && 'max-h-[700px]')} style={{ height }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 sm:px-5 py-3 sm:py-3.5 border-b border-surface-700/30 bg-surface-800/30">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20 flex-shrink-0">
            <BotIcon size={15} className="text-white" />
          </div>
          <div className="min-w-0">
            <span className="text-sm font-semibold text-surface-100">{title}</span>
            {hasProviders && (
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-[10px] text-surface-500 truncate">{displayProvider}</span>
                <span className="text-[10px] text-surface-600">/</span>
                <span className="text-[10px] text-violet-400/80 font-mono truncate">{displayModel}</span>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {!hasProviders && (
            <span className="text-[10px] text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-full border border-amber-500/20 hidden sm:inline">
              No providers
            </span>
          )}
          <button onClick={clearChat} className="p-2 rounded-xl text-surface-500 hover:text-surface-300 hover:bg-surface-700/50 transition-all duration-200" title="Clear chat">
            <Trash2Icon size={14} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-3 sm:space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              'flex gap-2.5 sm:gap-3 animate-slide-in-right',
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            {msg.role !== 'user' && (
              <div className={cn(
                'w-7 h-7 sm:w-8 sm:h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5',
                msg.is_error
                  ? 'bg-red-500/10 border border-red-500/20'
                  : 'bg-gradient-to-br from-violet-500/20 to-indigo-500/20 border border-violet-500/10'
              )}>
                {msg.is_error ? (
                  <span className="text-red-400 text-xs font-bold">!</span>
                ) : (
                  <BotIcon size={14} className="text-violet-400" />
                )}
              </div>
            )}
            <div
              className={cn(
                'max-w-[85%] sm:max-w-[80%] px-3 sm:px-4 py-2.5 sm:py-3 rounded-2xl text-sm leading-relaxed',
                msg.role === 'user'
                  ? 'bg-gradient-to-br from-violet-600/20 to-indigo-600/20 border border-violet-500/20 text-surface-100 rounded-br-md whitespace-pre-wrap'
                  : msg.is_error
                  ? 'bg-red-500/5 border border-red-500/10 text-red-300 rounded-bl-md whitespace-pre-wrap'
                  : 'bg-surface-800/60 border border-surface-700/30 text-surface-200 rounded-bl-md'
              )}
            >
              {msg.role === 'user' || msg.is_error ? (
                msg.content
              ) : (
                <div className="prose prose-invert prose-sm max-w-none prose-headings:text-surface-100 prose-p:text-surface-200 prose-li:text-surface-200 prose-strong:text-surface-100 prose-code:text-violet-300 prose-code:bg-surface-700/50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-pre:bg-surface-950 prose-pre:border prose-pre:border-surface-700/50 prose-a:text-violet-400 prose-a:no-underline hover:prose-a:underline prose-li:marker:text-violet-400">
                  <Markdown>{msg.content}</Markdown>
                </div>
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-xl bg-gradient-to-br from-surface-600 to-surface-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                <UserIcon size={14} className="text-surface-300" />
              </div>
            )}
          </div>
        ))}
        {sendMutation.isPending && !streaming && (
          <div className="flex gap-2.5 sm:gap-3 justify-start">
            <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-xl bg-gradient-to-br from-violet-500/20 to-indigo-500/20 border border-violet-500/10 flex items-center justify-center">
              <BotIcon size={14} className="text-violet-400" />
            </div>
            <div className="bg-surface-800/60 border border-surface-700/30 rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex gap-1.5">
                <div className="w-1.5 h-1.5 bg-violet-400/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-1.5 h-1.5 bg-violet-400/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-1.5 h-1.5 bg-violet-400/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Provider + Model Selectors + Input */}
      <div className="border-t border-surface-700/30 p-3 sm:p-4 bg-surface-800/20">
        {/* Provider and Model selector row */}
        {hasProviders && (
          <div className="flex gap-2 mb-3">
            {/* Provider selector */}
            <div className="relative flex-1 min-w-0">
              <label className="text-[10px] text-surface-500 mb-1 block">Provider</label>
              <div className="relative">
                <select
                  value={selectedProvider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="w-full appearance-none bg-surface-800/60 border border-surface-700/40 rounded-xl text-xs py-2 pl-3 pr-8 text-surface-200 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition-all cursor-pointer truncate"
                >
                  {providerList.map((p) => (
                    <option key={p.provider} value={p.provider}>
                      {getProviderLabel(p.provider)}
                    </option>
                  ))}
                </select>
                <ChevronDownIcon size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" />
              </div>
            </div>

            {/* Model selector */}
            <div className="relative flex-1 min-w-0">
              <label className="text-[10px] text-surface-500 mb-1 block">Model</label>
              <input
                type="text"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                placeholder={currentConfig?.default_model || 'model name'}
                className="w-full bg-surface-800/60 border border-surface-700/40 rounded-xl text-xs py-2 px-3 text-surface-200 font-mono placeholder:text-surface-600 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition-all"
              />
            </div>
          </div>
        )}

        {/* Input row */}
        <div className="flex gap-2 sm:gap-2.5 items-end">
          <div className="relative flex-1 min-w-0">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={hasProviders ? placeholder : 'Configure a provider first...'}
              className="w-full bg-surface-800/60 border border-surface-700/40 rounded-xl text-sm px-4 py-3 pr-12 resize-none min-h-[44px] max-h-[120px] text-surface-100 placeholder:text-surface-600 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition-all"
              rows={1}
              disabled={!hasProviders}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!input.trim() || sendMutation.isPending || !hasProviders}
            className={cn(
              'flex items-center justify-center w-11 h-11 rounded-xl transition-all duration-200 flex-shrink-0',
              input.trim() && !sendMutation.isPending && hasProviders
                ? 'bg-gradient-to-br from-violet-500 to-indigo-600 text-white shadow-lg shadow-violet-500/25 hover:shadow-violet-500/40 hover:scale-105 active:scale-95'
                : 'bg-surface-700/50 text-surface-500 cursor-not-allowed'
            )}
          >
            {sendMutation.isPending ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <SendIcon size={16} />
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
