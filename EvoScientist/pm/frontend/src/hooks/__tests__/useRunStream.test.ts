// EvoScientist/pm/frontend/src/hooks/__tests__/useRunStream.test.ts
import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useRunStream } from '../useRunStream'

describe('useRunStream', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // Mock sessionStorage
    Object.defineProperty(window, 'sessionStorage', {
      value: { getItem: vi.fn(() => 'test-token') },
      writable: true,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('starts with idle state when runId is null', () => {
    const { result } = renderHook(() => useRunStream(null))
    expect(result.current.output).toBe('')
    expect(result.current.isStreaming).toBe(false)
  })

  it('accumulates token events into output', async () => {
    const mockReader = {
      read: vi.fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode('data: {"type":"token","data":"Hello "}\n\n') })
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode('data: {"type":"token","data":"world"}\n\n') })
        .mockResolvedValueOnce({ done: true, value: undefined }),
    }
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => mockReader },
    })
    vi.stubGlobal('fetch', mockFetch)

    const { result } = renderHook(() => useRunStream('run123'))

    await act(async () => {
      await vi.runAllTimersAsync()
    })

    expect(result.current.output).toContain('Hello ')
    expect(result.current.output).toContain('world')
  })

  it('sets isStreaming false when done event received', async () => {
    const mockReader = {
      read: vi.fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode('data: {"type":"status","data":"done"}\n\n') })
        .mockResolvedValueOnce({ done: true, value: undefined }),
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => mockReader },
    }))

    const { result } = renderHook(() => useRunStream('run123'))

    await act(async () => {
      await vi.runAllTimersAsync()
    })

    expect(result.current.isStreaming).toBe(false)
  })
})
