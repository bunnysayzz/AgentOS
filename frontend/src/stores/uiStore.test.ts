import { beforeEach, describe, expect, it } from 'vitest'
import { useUIStore } from './uiStore'

describe('uiStore', () => {
  beforeEach(() => {
    localStorage.clear()
    useUIStore.setState({
      sidebarCollapsed: false,
      mobileSidebarOpen: false,
      theme: 'dark',
    })
    document.documentElement.className = ''
  })

  it('toggles the sidebar collapsed state', () => {
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(true)
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)
  })

  it('sets the mobile drawer state', () => {
    useUIStore.getState().setMobileSidebarOpen(true)
    expect(useUIStore.getState().mobileSidebarOpen).toBe(true)
    useUIStore.getState().setMobileSidebarOpen(false)
    expect(useUIStore.getState().mobileSidebarOpen).toBe(false)
  })

  it('setTheme updates the document class', () => {
    useUIStore.getState().setTheme('light')
    expect(document.documentElement.classList.contains('light')).toBe(true)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(useUIStore.getState().theme).toBe('light')
  })

  it('toggleTheme flips dark/light', () => {
    useUIStore.getState().setTheme('dark')
    useUIStore.getState().toggleTheme()
    expect(useUIStore.getState().theme).toBe('light')
    expect(document.documentElement.classList.contains('light')).toBe(true)
    useUIStore.getState().toggleTheme()
    expect(useUIStore.getState().theme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
