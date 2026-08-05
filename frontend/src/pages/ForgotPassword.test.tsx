import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import ForgotPassword from './ForgotPassword'
// The central stub in src/test/setup.ts mocks '@/services/firebase' with a
// vi.fn for sendPasswordResetEmailWrapper — import and stub per-test.
import { sendPasswordResetEmailWrapper } from '@/services/firebase'

function renderForgot() {
  return render(
    <MemoryRouter>
      <ForgotPassword />
    </MemoryRouter>,
  )
}

describe('ForgotPassword', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(sendPasswordResetEmailWrapper as any).mockResolvedValue(undefined)
  })

  it('renders the reset form', async () => {
    renderForgot()
    expect(await screen.findByRole('heading', { name: /reset your password/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('you@example.com')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send reset link/i })).toBeInTheDocument()
  })

  it('sends the reset email and shows the success screen', async () => {
    const user = userEvent.setup()
    renderForgot()

    await user.type(await screen.findByPlaceholderText('you@example.com'), 'a@b.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    expect(sendPasswordResetEmailWrapper).toHaveBeenCalledWith('a@b.com')
    expect(await screen.findByRole('heading', { name: /check your inbox/i })).toBeInTheDocument()
    expect(screen.getByText(/a@b\.com/)).toBeInTheDocument()
  })

  it('shows the success screen even for unknown accounts (anti-enumeration)', async () => {
    ;(sendPasswordResetEmailWrapper as any).mockRejectedValue({ code: 'auth/user-not-found' })
    const user = userEvent.setup()
    renderForgot()

    await user.type(await screen.findByPlaceholderText('you@example.com'), 'ghost@example.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    // Same success screen as a real account — no "account not found" leak.
    expect(await screen.findByRole('heading', { name: /check your inbox/i })).toBeInTheDocument()
    expect(screen.queryByText(/not found/i)).not.toBeInTheDocument()
  })

  it('shows an error for an invalid email address', async () => {
    // Syntactically valid address so the form's native email validation
    // passes and the (mocked) Firebase auth/invalid-email rejection is what
    // the page surfaces.
    ;(sendPasswordResetEmailWrapper as any).mockRejectedValue({ code: 'auth/invalid-email' })
    const user = userEvent.setup()
    renderForgot()

    await user.type(await screen.findByPlaceholderText('you@example.com'), 'bad@example.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    expect(await screen.findByText('Please enter a valid email address.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /check your inbox/i })).not.toBeInTheDocument()
  })

  it('resends from the success screen', async () => {
    const user = userEvent.setup()
    renderForgot()

    await user.type(await screen.findByPlaceholderText('you@example.com'), 'a@b.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))
    await screen.findByRole('heading', { name: /check your inbox/i })

    await user.click(screen.getByRole('button', { name: /resend email/i }))

    expect(sendPasswordResetEmailWrapper).toHaveBeenCalledTimes(2)
  })
})
