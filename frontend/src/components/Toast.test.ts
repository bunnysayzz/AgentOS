import { beforeEach, describe, expect, it } from 'vitest'
import { toast, useToastStore } from './Toast'

describe('toast store', () => {
  beforeEach(() => {
    useToastStore.getState().clearToasts()
  })

  it('adds a success toast', () => {
    toast.success('Saved', 'Everything is fine')
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0].type).toBe('success')
    expect(toasts[0].title).toBe('Saved')
    expect(toasts[0].message).toBe('Everything is fine')
  })

  it('adds error and info toasts with unique ids', () => {
    toast.error('Failed')
    toast.info('Heads up')
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(2)
    expect(new Set(toasts.map((t) => t.id)).size).toBe(2)
  })

  it('removes a toast by id', () => {
    const id = toast.warning('Careful')
    expect(useToastStore.getState().toasts).toHaveLength(1)
    useToastStore.getState().removeToast(id)
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('clearToasts empties the queue', () => {
    toast.success('a')
    toast.error('b')
    useToastStore.getState().clearToasts()
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })
})
