import Paper from '@mui/material/Paper'
import { useImperativeHandle, useLayoutEffect, useRef, useState, type Ref } from 'react'
import type { TripPlan } from '@/api/schemas'
import { CheckpointTooltipContent } from './CheckpointTooltip'
import { OVERLAY_SHADOW } from './overlay'
import { RouteTooltipContent } from './RouteTooltip'
import {
  anchoredPosition,
  NO_TOOLTIP,
  tooltipReducer,
  type LngLat,
  type TooltipBounds,
  type TooltipEvent,
  type TooltipState,
} from './tooltipState'

export interface TooltipPosition {
  x: number
  y: number
  width: number
  height: number
}

export interface MapTooltipHandle {
  send: (event: TooltipEvent, position?: TooltipPosition, anchor?: LngLat) => void
  follow: (project: (lngLat: LngLat) => { x: number; y: number }, bounds: TooltipBounds) => void
}

const GAP = 14
const EDGE = 8

function place(el: HTMLElement, { x, y, width, height }: TooltipPosition) {
  // On a short map (landscape phone) the card scrolls instead of spilling onto the panel.
  el.style.maxHeight = `${Math.max(0, height - EDGE * 2)}px`
  const w = el.offsetWidth
  const h = el.offsetHeight
  const left = x + GAP + w > width ? x - GAP - w : x + GAP
  const top = y + GAP + h > height ? y - GAP - h : y + GAP
  const clampedLeft = Math.max(EDGE, Math.min(left, width - w - EDGE))
  const clampedTop = Math.max(EDGE, Math.min(top, height - h - EDGE))
  el.style.transform = `translate3d(${clampedLeft}px, ${clampedTop}px, 0)`
}

// Owns hover/pin state so pointer moves never re-render the map. Moves within the same
// target, and map moves under a pinned card, only reposition the element directly.
export function MapTooltip({ plan, ref }: { plan: TripPlan; ref: Ref<MapTooltipHandle> }) {
  const [state, setState] = useState<TooltipState>(NO_TOOLTIP)
  const stateRef = useRef(state)
  const boxRef = useRef<HTMLDivElement>(null)
  const positionRef = useRef<TooltipPosition | null>(null)
  const anchorRef = useRef<LngLat | null>(null)

  useImperativeHandle(ref, () => {
    const commit = (next: TooltipState) => {
      if (next === stateRef.current) return
      stateRef.current = next
      if (!next.pinned) anchorRef.current = null
      setState(next)
    }
    return {
      send(event, position, anchor) {
        const next = tooltipReducer(stateRef.current, event)
        const follows = next.target !== null && (event.type === 'tap' || !next.pinned)
        if (follows && position) {
          positionRef.current = position
          if (boxRef.current) place(boxRef.current, position)
        }
        if (event.type === 'tap' && next.pinned) anchorRef.current = anchor ?? null
        commit(next)
      },
      follow(project, bounds) {
        const anchor = anchorRef.current
        if (!stateRef.current.pinned || !anchor) return
        const position = anchoredPosition(anchor, project, bounds)
        if (!position) {
          commit(NO_TOOLTIP)
          return
        }
        positionRef.current = position
        if (boxRef.current) place(boxRef.current, position)
      },
    }
  }, [])

  useLayoutEffect(() => {
    if (boxRef.current && positionRef.current) place(boxRef.current, positionRef.current)
  }, [state])

  const { target } = state
  if (!target) return null

  const route =
    target.kind === 'route' ? plan.routes.find((r) => r.id === target.routeId) : undefined
  if (target.kind === 'route' && !route) return null

  return (
    <Paper
      ref={boxRef}
      role="tooltip"
      elevation={0}
      data-pinned={state.pinned || undefined}
      sx={(theme) => ({
        position: 'absolute',
        left: 0,
        top: 0,
        width: target.kind === 'route' ? 'max-content' : 272,
        minWidth: target.kind === 'route' ? 280 : undefined,
        maxWidth: `min(360px, calc(100% - ${EDGE * 2}px))`,
        overflowY: 'auto',
        pointerEvents: state.pinned ? 'auto' : 'none',
        zIndex: 3,
        p: 1.5,
        border: 1,
        borderColor: state.pinned ? 'primary.main' : 'divider',
        boxShadow: `0 6px 20px ${OVERLAY_SHADOW.light}`,
        ...theme.applyStyles('dark', { boxShadow: `0 6px 20px ${OVERLAY_SHADOW.dark}` }),
      })}
    >
      {route ? (
        <RouteTooltipContent route={route} recommended={route.id === plan.recommended_route_id} />
      ) : target.kind === 'checkpoint' ? (
        <CheckpointTooltipContent datum={target.datum} />
      ) : null}
    </Paper>
  )
}
