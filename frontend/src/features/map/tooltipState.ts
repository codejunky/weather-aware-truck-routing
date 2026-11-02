import { targetRouteId, type MapTarget } from './layers'

export interface TooltipState {
  target: MapTarget | null
  pinned: boolean
}

export type TooltipEvent =
  | { type: 'hover'; target: MapTarget | null }
  | { type: 'tap'; target: MapTarget | null }
  | { type: 'clear' }

export const NO_TOOLTIP: TooltipState = { target: null, pinned: false }

function sameTarget(a: MapTarget | null, b: MapTarget | null) {
  if (a === null || b === null) return a === b
  if (a.kind === 'route' && b.kind === 'route') return a.routeId === b.routeId
  if (a.kind === 'checkpoint' && b.kind === 'checkpoint') return a.datum === b.datum
  return false
}

// Hover never disturbs a pinned tooltip; a tap pins its target, and a tap on nothing clears.
export function tooltipReducer(state: TooltipState, event: TooltipEvent): TooltipState {
  switch (event.type) {
    case 'hover':
      if (state.pinned || sameTarget(state.target, event.target)) return state
      return { target: event.target, pinned: false }
    case 'tap':
      if (event.target === null) return state.target === null ? state : NO_TOOLTIP
      return { target: event.target, pinned: true }
    case 'clear':
      return state.target === null ? state : NO_TOOLTIP
  }
}

export type LngLat = [number, number]

export interface TooltipBounds {
  width: number
  height: number
}

// Mouse clicks only select; hover already shows the tooltip. Touch and pens may not hover, so a tap pins.
export function clickIntent(
  target: MapTarget | null,
  pointerType: string | null,
): { selectRouteId: string | null; tooltip: TooltipEvent | null } {
  const selectRouteId = target ? targetRouteId(target) : null
  if (pointerType !== 'mouse') return { selectRouteId, tooltip: { type: 'tap', target } }
  return { selectRouteId, tooltip: null }
}

// Where a pinned anchor sits after the map moved, or null once it leaves the visible area.
export function anchoredPosition(
  anchor: LngLat,
  project: (lngLat: LngLat) => { x: number; y: number },
  { width, height }: TooltipBounds,
) {
  const { x, y } = project(anchor)
  if (x < 0 || y < 0 || x > width || y > height) return null
  return { x, y, width, height }
}
