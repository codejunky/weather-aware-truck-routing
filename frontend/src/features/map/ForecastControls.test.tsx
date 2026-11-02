import { fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import type { HeatmapMetric } from '@/api/schemas'
import { renderWithProviders } from '@/test/utils'
import { ForecastControls } from './ForecastControls'

function Harness() {
  const [hour, setHour] = useState(0)
  const [metric, setMetric] = useState<HeatmapMetric>('risk')
  const [on, setOn] = useState(true)
  return (
    <ForecastControls
      start="2026-11-03T08:00:00"
      hour={hour}
      maxHour={48}
      onHourChange={setHour}
      metric={metric}
      onMetricChange={setMetric}
      scheme="light"
      heatmapOn={on}
      onHeatmapChange={setOn}
      heatmapFaded={false}
    />
  )
}

describe('ForecastControls', () => {
  it('slider drag stops playback', async () => {
    renderWithProviders(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: 'Play forecast' }))
    expect(screen.getByRole('button', { name: 'Pause forecast' })).toBeInTheDocument()

    const slider = screen.getByRole('slider', { name: 'Forecast hour' })
    fireEvent.change(slider, { target: { value: 20 } })

    expect(screen.getByRole('button', { name: 'Play forecast' })).toBeInTheDocument()
    expect(slider).toHaveAttribute('aria-valuetext', '+20h · Wed 4 AM')
  })
})
