import { useEffect, useEffectEvent, useState } from 'react'

interface Options {
  hour: number
  onHourChange: (hour: number) => void
  max: number
  enabled?: boolean
  stepMs?: number
}

export function useForecastPlayback({
  hour,
  onHourChange,
  max,
  enabled = true,
  stepMs = 600,
}: Options) {
  const [playing, setPlaying] = useState(false)

  // Turning reduced motion on mid-play stops playback for good, it does not pause it.
  if (playing && !enabled) setPlaying(false)

  const tick = useEffectEvent(() => {
    const next = Math.min(hour + 1, max)
    onHourChange(next)
    if (next >= max) setPlaying(false)
  })

  useEffect(() => {
    if (!playing) return
    const timer = setInterval(tick, stepMs)
    return () => {
      clearInterval(timer)
    }
  }, [playing, stepMs])

  const toggle = () => {
    if (playing) {
      setPlaying(false)
      return
    }
    if (!enabled) return
    if (hour >= max) onHourChange(0)
    setPlaying(true)
  }

  const stop = () => {
    setPlaying(false)
  }

  return { playing, toggle, stop }
}
