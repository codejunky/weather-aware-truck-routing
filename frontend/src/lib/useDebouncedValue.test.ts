import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useDebouncedValue } from './useDebouncedValue'

afterEach(() => {
  vi.useRealTimers()
})

describe('useDebouncedValue', () => {
  it('only updates after the delay has passed without changes', () => {
    vi.useFakeTimers()
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: 'chi' },
    })
    rerender({ value: 'chic' })
    act(() => {
      vi.advanceTimersByTime(200)
    })
    rerender({ value: 'chica' })
    act(() => {
      vi.advanceTimersByTime(200)
    })
    expect(result.current).toBe('chi')
    act(() => {
      vi.advanceTimersByTime(100)
    })
    expect(result.current).toBe('chica')
  })
})
