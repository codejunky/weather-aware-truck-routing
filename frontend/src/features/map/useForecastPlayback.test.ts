import { act, renderHook } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useForecastPlayback } from './useForecastPlayback'

function usePlayback({ start, enabled = true }: { start: number; enabled?: boolean }) {
  const [hour, setHour] = useState(start)
  const playback = useForecastPlayback({ hour, onHourChange: setHour, max: 48, enabled })
  return { hour, ...playback }
}

function advance(steps: number) {
  for (let i = 0; i < steps; i++) {
    act(() => {
      vi.advanceTimersByTime(600)
    })
  }
}

describe('useForecastPlayback', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('steps one hour every 600ms', () => {
    const { result } = renderHook(() => usePlayback({ start: 0 }))
    act(() => {
      result.current.toggle()
    })
    act(() => {
      vi.advanceTimersByTime(599)
    })
    expect(result.current.hour).toBe(0)
    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(result.current.hour).toBe(1)
    advance(2)
    expect(result.current.hour).toBe(3)
  })

  it('playback hook stops at 48', () => {
    const { result } = renderHook(() => usePlayback({ start: 45 }))
    act(() => {
      result.current.toggle()
    })
    advance(10)
    expect(result.current.hour).toBe(48)
    expect(result.current.playing).toBe(false)
  })

  it('restarts from 0 when played at the end', () => {
    const { result } = renderHook(() => usePlayback({ start: 48 }))
    act(() => {
      result.current.toggle()
    })
    expect(result.current.hour).toBe(0)
    expect(result.current.playing).toBe(true)
  })

  it('does not autoplay when disabled', () => {
    const { result } = renderHook(() => usePlayback({ start: 0, enabled: false }))
    act(() => {
      result.current.toggle()
    })
    advance(5)
    expect(result.current.playing).toBe(false)
    expect(result.current.hour).toBe(0)
  })

  it('stops for good when it becomes disabled mid-play', () => {
    const { result, rerender } = renderHook(
      (props: { enabled: boolean }) => usePlayback({ start: 0, enabled: props.enabled }),
      { initialProps: { enabled: true } },
    )
    act(() => {
      result.current.toggle()
    })
    advance(2)
    expect(result.current.hour).toBe(2)

    rerender({ enabled: false })
    advance(3)
    expect(result.current.playing).toBe(false)
    expect(result.current.hour).toBe(2)

    rerender({ enabled: true })
    advance(3)
    expect(result.current.playing).toBe(false)
    expect(result.current.hour).toBe(2)
  })
})
