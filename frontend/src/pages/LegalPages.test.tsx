import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Terms from './Terms'
import Privacy from './Privacy'
import Login from './Login'

describe('Terms page', () => {
  it('renders the Terms of Service with key sections', () => {
    render(
      <MemoryRouter>
        <Terms />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Terms of Service')
    expect(screen.getByText('1. Acceptance of Terms')).toBeInTheDocument()
    expect(screen.getByText('8. Fees & Plans')).toBeInTheDocument()
    expect(screen.getByText('11. Limitation of Liability')).toBeInTheDocument()
    // Cross-link to privacy
    expect(screen.getByRole('link', { name: /privacy policy/i })).toBeInTheDocument()
  })
})

describe('Privacy page', () => {
  it('renders the Privacy Policy with GDPR sections', () => {
    render(
      <MemoryRouter>
        <Privacy />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Privacy Policy')
    expect(screen.getByText('8. Your Rights (GDPR & CCPA)')).toBeInTheDocument()
    expect(screen.getByText('7. Data Retention')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /terms of service/i })).toBeInTheDocument()
  })
})

describe('Login page legal links', () => {
  it('links to Terms and Privacy from the login form', async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    )
    // The login page shows a google-checking spinner briefly; the form
    // renders after checkGoogleRedirect calls onNoRedirect (stubbed sync).
    const terms = await screen.findByRole('link', { name: /^terms$/i })
    expect(terms).toHaveAttribute('href', '/terms')
    const privacy = screen.getByRole('link', { name: /privacy policy/i })
    expect(privacy).toHaveAttribute('href', '/privacy')
  })
})
