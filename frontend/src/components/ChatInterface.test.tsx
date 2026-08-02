import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ChatInterface from './ChatInterface'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import api from '@/services/api'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

function renderChat() {
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatInterface title="Test Chat" placeholder="Type a message..." />
    </QueryClientProvider>,
  )
}

describe('ChatInterface', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the welcome message and configured provider', async () => {
    ;(api.get as any).mockResolvedValue({
      data: [
        { provider: 'openai', default_model: 'gpt-4o-mini', is_configured: true },
        { provider: 'deepseek', default_model: 'deepseek-chat', is_configured: true },
      ],
    })
    renderChat()
    expect(await screen.findByText(/hello! i'm an ai assistant/i)).toBeInTheDocument()
    expect(await screen.findByRole('combobox')).toBeInTheDocument()
    expect(await screen.findByDisplayValue('gpt-4o-mini')).toBeInTheDocument()
  })

  it('sends a message and renders the assistant reply', async () => {
    ;(api.get as any).mockResolvedValue({
      data: [{ provider: 'openai', default_model: 'gpt-4o-mini', is_configured: true }],
    })
    ;(api.post as any).mockResolvedValue({
      data: {
        choices: [{ message: { content: 'Hello back!' } }],
        model: 'gpt-4o-mini',
        provider: 'openai',
        usage: { prompt_tokens: 5, completion_tokens: 3, total_tokens: 8 },
      },
    })

    const user = userEvent.setup()
    renderChat()

    const input = await screen.findByPlaceholderText('Type a message...')
    await user.type(input, 'hello{enter}')

    expect(await screen.findByText('Hello back!')).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith('/mcp/chat/completions', expect.objectContaining({
      model: 'gpt-4o-mini',
      messages: expect.arrayContaining([
        { role: 'user', content: 'hello' },
      ]),
    }))
  })

  it('disables input until a provider is configured', async () => {
    ;(api.get as any).mockResolvedValue({ data: [] })
    renderChat()
    const input = await screen.findByPlaceholderText('Configure a provider first in the Providers page...')
    expect(input).toBeDisabled()
    expect(screen.getByText('No providers configured')).toBeInTheDocument()
  })

  it('clears the chat history', async () => {
    ;(api.get as any).mockResolvedValue({
      data: [{ provider: 'openai', default_model: 'gpt-4o-mini', is_configured: true }],
    })
    const user = userEvent.setup()
    renderChat()

    const input = await screen.findByPlaceholderText('Type a message...')
    await user.type(input, 'first message')
    await user.click(screen.getByTitle('Clear chat'))

    expect(await screen.findByText(/chat cleared!/i)).toBeInTheDocument()
  })
})
