import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import api from '@/services/api'
import { cn } from '@/utils/cn'
import { SendIcon, BotIcon, UserIcon, Trash2Icon } from '@/components/Icons'
import { toast } from '@/components/Toast'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at?: string
  is_error?: boolean
}

interface ChatInterfaceProps {
  /** Agent system prompt (optional) */
  systemPrompt?: string
  /** Default model to use */
  defaultModel?: string
  /** Workspace ID for context */
  workspaceId?: string
  /** Show provider selector */
  showProviderSelector?: boolean
  /** Height constraint */
  height?: string
  /** Title for the chat */
  title?: string
  /** Placeholder text */
  placeholder?: string
  /** If true, allow full height growth (no max-h) */
  fullHeight?: boolean
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
        ? `👋 I'm ready! I'll use the system prompt you configured. Ask me anything.`
        : `👋 Hello! I'm an AI assistant. Send me a message and I'll respond using the configured model.`,
    },
  ])
  const [input, setInput] = useState('')
  const [selectedModel, setSelectedModel] = useState(defaultModel)
  const [selectedProvider, setSelectedProvider] = useState<string>('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Fetch available providers for the dropdown
  const { data: providers } = useQuery({
    queryKey: ['provider-configs'],
    queryFn: () => api.get('/mcp/providers').then((r) => r.data),
    enabled: showProviderSelector,
  })

  const providerList: any[] = Array.isArray(providers) ? providers.filter((p: any) => p.is_configured) : []

  // Set default provider if available
  useEffect(() => {
    if (providerList.length > 0 && !selectedProvider) {
      setSelectedProvider(providerList[0].provider)
    }
  }, [providerList, selectedProvider])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Send message mutation
  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      // Build messages array
      const chatMessages: any[] = []
      if (systemPrompt) {
        chatMessages.push({ role: 'system', content: systemPrompt })
      }
      // Add previous messages (excluding welcome)
      for (const msg of messages) {
        if (msg.id !== 'welcome' && !msg.is_error) {
          chatMessages.push({ role: msg.role, content: msg.content })
        }
      }
      // Add the new user message
      chatMessages.push({ role: 'user', content })

      const response = await api.post('/mcp/chat/completions', {
        model: selectedModel,
        messages: chatMessages,
        temperature: 0.7,
        max_tokens: 2048,
        stream: false,
        ...(workspaceId ? { workspace_id: workspaceId } : {}),
      })
      return response.data
    },
    onSuccess: (data: any) => {
      const responseContent = data.choices?.[0]?.message?.content || ''
      const modelUsed = data.model || selectedModel
      const providerUsed = data.provider || selectedProvider

      setMessages((prev) => [
        ...prev,
        {
          id: `resp-${Date.now()}`,
          role: 'assistant',
          content: responseContent || '(empty response)',
          created_at: new Date().toISOString(),
        },
      ])

      // Show token usage
      if (data.usage) {
        const { prompt_tokens, completion_tokens, total_tokens } = data.usage
        console.log(`[${providerUsed}/${modelUsed}] Tokens: ${total_tokens} (${prompt_tokens}in + ${completion_tokens}out)`)
      }
    },
    onError: (err: any) => {
      const errorMsg = err.response?.data?.detail || err.message || 'Request failed'
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: `⚠️ Error: ${errorMsg}`,
          is_error: true,
        },
      ])
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
          ? `👋 Chat cleared! I'll still use your system prompt.`
          : `👋 Chat cleared! Send a new message to start.`,
      },
    ])
  }

  const hasProviders = providerList.length > 0

  return (
    <div className={cn('flex flex-col glass-panel overflow-hidden', !fullHeight && 'max-h-[700px]')} style={{ height }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-700/30">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
            <BotIcon size={14} className="text-white" />
          </div>
          <span className="text-sm font-medium">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          {!hasProviders && (
            <span className="text-[10px] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full">
              No providers configured
            </span>
          )}
          <button onClick={clearChat} className="p-1.5 rounded-lg text-surface-500 hover:text-surface-300 hover:bg-surface-800 transition-all" title="Clear chat">
            <Trash2Icon size={14} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              'flex gap-3 animate-slide-in-right',
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            {msg.role !== 'user' && (
              <div className={cn(
                'w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-1',
                msg.is_error
                  ? 'bg-red-500/10 border border-red-500/20'
                  : 'bg-gradient-to-br from-primary-500/20 to-primary-600/20 border border-primary-500/10'
              )}>
                {msg.is_error ? (
                  <span className="text-red-400 text-xs font-bold">!</span>
                ) : (
                  <BotIcon size={14} className="text-primary-400" />
                )}
              </div>
            )}
            <div
              className={cn(
                'max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap',
                msg.role === 'user'
                  ? 'bg-primary-500/10 border border-primary-500/20 text-surface-200 rounded-br-md'
                  : msg.is_error
                  ? 'bg-red-500/5 border border-red-500/10 text-red-300 rounded-bl-md'
                  : 'bg-surface-800/50 border border-surface-700/30 text-surface-200 rounded-bl-md'
              )}
            >
              {msg.content}
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-xl bg-surface-700 flex items-center justify-center flex-shrink-0 mt-1">
                <UserIcon size={14} className="text-surface-300" />
              </div>
            )}
          </div>
        ))}
        {sendMutation.isPending && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-xl bg-surface-800 border border-surface-700/30 flex items-center justify-center">
              <BotIcon size={14} className="text-primary-400" />
            </div>
            <div className="bg-surface-800/50 border border-surface-700/30 rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-surface-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-surface-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-surface-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Model/Provider Selector + Input */}
      <div className="border-t border-surface-700/30 p-3 space-y-2">
        {/* Provider + Model selector row */}
        {hasProviders && (
          <div className="flex gap-2">
            <select
              value={selectedProvider}
              onChange={(e) => setSelectedProvider(e.target.value)}
              className="input-field text-xs py-1.5 flex-1"
            >
              {providerList.map((p: any) => (
                <option key={p.provider} value={p.provider}>
                  {p.provider} {p.default_model ? `(${p.default_model})` : ''}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              placeholder="model name"
              className="input-field text-xs py-1.5 flex-1 font-mono"
            />
          </div>
        )}

        {/* Input row */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={hasProviders ? placeholder : 'Configure a provider first in the Providers page...'}
              className="input-field w-full resize-none text-sm pr-10 py-2.5 min-h-[40px] max-h-[120px]"
              rows={1}
              disabled={!hasProviders}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!input.trim() || sendMutation.isPending || !hasProviders}
            className={cn(
              'btn-primary flex items-center justify-center w-10 h-10 p-0 rounded-xl',
              'disabled:opacity-30 disabled:cursor-not-allowed'
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
