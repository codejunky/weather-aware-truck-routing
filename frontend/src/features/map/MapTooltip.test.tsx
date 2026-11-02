import { act, screen, within } from '@testing-library/react'
import { createRef } from 'react'
import { describe, expect, it } from 'vitest'
import { TripPlanSchema } from '@/api/schemas'
import { formatDuration, formatEtaParts, formatMiles } from '@/lib/format'
import fixture from '@/test/fixtures/plan.json'
import { renderWithProviders } from '@/test/utils'
import { MapTooltip, type MapTooltipHandle } from './MapTooltip'

const plan = TripPlanSchema.parse(fixture)
const position = { x: 100, y: 100, width: 800, height: 600 }

function setup() {
  const ref = createRef<MapTooltipHandle>()
  renderWithProviders(<MapTooltip ref={ref} plan={plan} />)
  const send: MapTooltipHandle['send'] = (event, pos, anchor) => {
    act(() => {
      ref.current?.send(event, pos, anchor)
    })
  }
  return send
}

function setupWithHandle() {
  const ref = createRef<MapTooltipHandle>()
  renderWithProviders(<MapTooltip ref={ref} plan={plan} />)
  return ref
}

describe('MapTooltip', () => {
  it('route hover/tap tooltip renders the summary fields', () => {
    const send = setup()
    const route = plan.routes.find((r) => r.id === plan.recommended_route_id)
    if (!route) throw new Error('fixture lacks the recommended route')

    send({ type: 'hover', target: { kind: 'route', routeId: route.id } }, position)
    const tip = within(screen.getByRole('tooltip'))
    expect(tip.getByText(route.summary)).toBeInTheDocument()
    expect(tip.getByText(`Route ${route.id}`)).toBeInTheDocument()
    expect(tip.getByText('Recommended')).toBeInTheDocument()
    expect(tip.getByText(formatMiles(route.distance_mi))).toBeInTheDocument()
    expect(tip.getByText(formatDuration(route.duration_s))).toBeInTheDocument()
    const arrival = formatEtaParts(route.arrival_at)
    expect(tip.getByText(arrival.time)).toBeInTheDocument()
    expect(tip.getByRole('img', { name: /Miles by risk/ })).toBeInTheDocument()

    send({ type: 'tap', target: { kind: 'route', routeId: route.id } }, position)
    expect(screen.getByRole('tooltip')).toHaveAttribute('data-pinned', 'true')
  })

  it('a pinned tooltip survives hover-out and clears on an empty tap', () => {
    const send = setup()
    send({ type: 'tap', target: { kind: 'route', routeId: 'B' } }, position)
    send({ type: 'hover', target: null }, position)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()

    send({ type: 'tap', target: null }, position)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('a pinned tooltip follows its anchor and clears when it leaves the map', () => {
    const ref = setupWithHandle()
    act(() => {
      ref.current?.send(
        { type: 'tap', target: { kind: 'route', routeId: 'A' } },
        position,
        [-95, 40],
      )
    })
    const tip = screen.getByRole('tooltip')
    const bounds = { width: 800, height: 600 }

    act(() => {
      ref.current?.follow(() => ({ x: 300, y: 200 }), bounds)
    })
    expect(tip.style.transform).toBe('translate3d(314px, 214px, 0)')

    act(() => {
      ref.current?.follow(() => ({ x: 900, y: 200 }), bounds)
    })
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })
})
