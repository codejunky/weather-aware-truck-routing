import Stack from '@mui/material/Stack'
import { useRef, type KeyboardEvent } from 'react'
import type { TripPlan } from '@/api/schemas'
import { RouteCard } from './RouteCard'

interface RouteListProps {
  plan: TripPlan
  selectedRouteId: string | null
  onSelect: (id: string) => void
}

const STEPS: Record<string, number> = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }

export function RouteList({ plan, selectedRouteId, onSelect }: RouteListProps) {
  const cards = useRef(new Map<string, HTMLDivElement>())
  const isRecommended = (id: string) => id === plan.recommended_route_id
  const routes = plan.routes.toSorted(
    (a, b) => Number(isRecommended(b.id)) - Number(isRecommended(a.id)) || a.rank - b.rank,
  )
  const tabStop = routes.some((r) => r.id === selectedRouteId) ? selectedRouteId : routes[0]?.id

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>, index: number) => {
    let next: number | undefined
    const step = STEPS[event.key]
    if (step !== undefined) next = (index + step + routes.length) % routes.length
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = routes.length - 1
    else if (event.key === 'Enter' || event.key === ' ') next = index
    const route = next === undefined ? undefined : routes[next]
    if (!route) return
    event.preventDefault()
    onSelect(route.id)
    cards.current.get(route.id)?.focus()
  }

  return (
    <Stack role="radiogroup" aria-label="Route options" spacing={1.5}>
      {routes.map((route, index) => (
        <RouteCard
          key={route.id}
          route={route}
          recommended={isRecommended(route.id)}
          selected={route.id === selectedRouteId}
          focusable={route.id === tabStop}
          onSelect={onSelect}
          onKeyDown={(event) => {
            handleKeyDown(event, index)
          }}
          cardRef={(el) => {
            if (el) cards.current.set(route.id, el)
            else cards.current.delete(route.id)
          }}
        />
      ))}
    </Stack>
  )
}
