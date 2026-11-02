import { describe, expect, it } from 'vitest'
import { TripPlanSchema } from '@/api/schemas'
import fixture from '@/test/fixtures/plan.json'
import {
  checkpointLayer,
  LAYER_IDS,
  targetFromPick,
  type CheckpointDatum,
  type MapTarget,
} from './layers'
import { anchoredPosition, clickIntent, NO_TOOLTIP, tooltipReducer } from './tooltipState'

const plan = TripPlanSchema.parse(fixture)
const datum = (checkpointLayer(plan.routes, 'A').props.data as CheckpointDatum[])[0]
if (!datum) throw new Error('fixture has no checkpoints')
const checkpoint: MapTarget = { kind: 'checkpoint', datum }
const routeB: MapTarget = { kind: 'route', routeId: 'B' }

describe('tooltipReducer', () => {
  it('tap pins and empty-map tap clears', () => {
    const pinned = tooltipReducer(NO_TOOLTIP, { type: 'tap', target: checkpoint })
    expect(pinned).toEqual({ target: checkpoint, pinned: true })

    const afterHover = tooltipReducer(pinned, { type: 'hover', target: routeB })
    expect(afterHover).toBe(pinned)
    expect(tooltipReducer(pinned, { type: 'hover', target: null })).toBe(pinned)

    expect(tooltipReducer(pinned, { type: 'tap', target: null })).toEqual(NO_TOOLTIP)
  })

  it('hover follows the pointer target and keeps identity for the same object', () => {
    const hovered = tooltipReducer(NO_TOOLTIP, { type: 'hover', target: routeB })
    expect(hovered).toEqual({ target: routeB, pinned: false })
    expect(
      tooltipReducer(hovered, { type: 'hover', target: { kind: 'route', routeId: 'B' } }),
    ).toBe(hovered)
    expect(tooltipReducer(hovered, { type: 'hover', target: null })).toEqual(NO_TOOLTIP)
  })

  it('clear drops a pinned tooltip', () => {
    const pinned = tooltipReducer(NO_TOOLTIP, { type: 'tap', target: routeB })
    expect(tooltipReducer(pinned, { type: 'clear' })).toEqual(NO_TOOLTIP)
  })
})

describe('targetFromPick', () => {
  it('narrows picks by layer id', () => {
    expect(targetFromPick({ layer: { id: LAYER_IDS.checkpoints }, object: datum })).toEqual(
      checkpoint,
    )
    const route = { id: 'C', path: [] }
    expect(targetFromPick({ layer: { id: LAYER_IDS.selectedRouteCasing }, object: route })).toEqual(
      {
        kind: 'route',
        routeId: 'C',
      },
    )
    expect(targetFromPick({ layer: { id: LAYER_IDS.heatmap }, object: route })).toBeNull()
    expect(targetFromPick({ layer: null, object: undefined })).toBeNull()
  })
})

describe('clickIntent', () => {
  it('a mouse click selects without pinning', () => {
    expect(clickIntent(routeB, 'mouse')).toEqual({ selectRouteId: 'B', tooltip: null })
    expect(clickIntent(checkpoint, 'mouse')).toEqual({
      selectRouteId: datum.routeId,
      tooltip: null,
    })
    expect(clickIntent(null, 'mouse')).toEqual({ selectRouteId: null, tooltip: null })
  })

  it('a pen tap pins like touch, since pens may not hover', () => {
    expect(clickIntent(routeB, 'pen')).toEqual({
      selectRouteId: 'B',
      tooltip: { type: 'tap', target: routeB },
    })
  })

  it('a touch tap pins, and a touch tap on nothing clears', () => {
    expect(clickIntent(checkpoint, 'touch')).toEqual({
      selectRouteId: datum.routeId,
      tooltip: { type: 'tap', target: checkpoint },
    })
    expect(clickIntent(null, 'touch')).toEqual({
      selectRouteId: null,
      tooltip: { type: 'tap', target: null },
    })
  })
})

describe('anchoredPosition', () => {
  const bounds = { width: 400, height: 300 }

  it('follows the projected anchor as the map moves', () => {
    let offset = 0
    const project = ([lng, lat]: [number, number]) => ({ x: lng * 10 + offset, y: lat * 10 })
    expect(anchoredPosition([10, 12], project, bounds)).toEqual({ x: 100, y: 120, ...bounds })
    offset = 150
    expect(anchoredPosition([10, 12], project, bounds)).toEqual({ x: 250, y: 120, ...bounds })
  })

  it('returns null once the anchor leaves the visible area', () => {
    const project = () => ({ x: 420, y: 50 })
    expect(anchoredPosition([0, 0], project, bounds)).toBeNull()
  })
})
