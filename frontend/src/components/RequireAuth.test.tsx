import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom'
import RequireAuth from './RequireAuth'
import { useAuthStore } from '@/stores/authStore'

function RedirectProbe() {
  const [params] = useSearchParams()
  return <div>login-page redirect={params.get('redirect')}</div>
}

function renderGated(initialPath = '/profile') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<RequireAuth />}>
          <Route path="/profile" element={<div>Profile content</div>} />
          <Route path="/api-keys" element={<div>ApiKeys content</div>} />
        </Route>
        <Route path="/login" element={<RedirectProbe />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RequireAuth', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    })
  })

  it('redirects guests to /login with the intended destination', async () => {
    renderGated('/api-keys')
    // The guard must NOT render the page — it must bounce to /login and
    // remember where the guest was headed.
    expect(await screen.findByText('login-page redirect=/api-keys')).toBeInTheDocument()
    expect(screen.queryByText('ApiKeys content')).not.toBeInTheDocument()
  })

  it('lets authenticated users through to the page', async () => {
    useAuthStore.getState().setAuth('access', 'refresh', {
      id: 'u1', email: 'a@b.com', username: 'a', fullName: 'A',
    })
    renderGated()
    expect(await screen.findByText('Profile content')).toBeInTheDocument()
  })
})
