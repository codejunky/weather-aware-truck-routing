import type { PathLayer, ScatterplotLayer } from '@deck.gl/layers'
import { describe, expect, it } from 'vitest'
import { TripPlanSchema } from '@/api/schemas'
import { riskRgb } from '@/lib/risk'
import fixture from '@/test/fixtures/plan.json'
import {
  buildHeatmapGrid,
  checkpointLayer,
  decodeRoutes,
  heatmapLayer,
  METRICS,
  routeLayers,
  type CheckpointDatum,
  type DecodedRoute,
} from './layers'

const plan = TripPlanSchema.parse(fixture)
const routes = decodeRoutes(plan.routes)

type Accessor = (d: unknown, info: { index: number }) => unknown

const call = (accessor: unknown, d: unknown, index = 0) => (accessor as Accessor)(d, { index })

function must<T>(value: T | undefined): T {
  if (value === undefined) throw new Error('missing fixture value')
  return value
}

describe('routeLayers', () => {
  it('selected route drawn last and wider', () => {
    const layers: PathLayer<DecodedRoute>[] = routeLayers(routes, 'B', 'light')
    const top = must(layers.at(-1))
    const bottom = must(layers.find((l) => l.id === 'routes'))

    expect(top.props.data).toEqual([expect.objectContaining({ id: 'B' })])
    expect(bottom.props.data).toEqual([
      expect.objectContaining({ id: 'A' }),
      expect.objectContaining({ id: 'C' }),
    ])
    expect(layers.indexOf(bottom)).toBeLessThan(layers.length - 1)
    expect(call(top.props.getWidth, routes[1])).toBe(6)
    expect(call(bottom.props.getWidth, routes[0])).toBe(4)
  })

  it('decodes polylines at precision 6 into [lon, lat]', () => {
    const [lon, lat] = must(routes[0]?.path[0])
    expect(lon).toBeCloseTo(-87.63, 1)
    expect(lat).toBeCloseTo(41.88, 1)
  })
})

describe('checkpointLayer', () => {
  it('checkpoint colors follow level', () => {
    const layer: ScatterplotLayer<CheckpointDatum> = checkpointLayer(plan.routes, 'A')
    const data = layer.props.data as CheckpointDatum[]

    for (const d of data) {
      const [r, g, b, a] = call(layer.props.getFillColor, d) as number[]
      expect([r, g, b]).toEqual([...riskRgb(d.checkpoint.level)])
      expect(a).toBe(d.routeId === 'A' ? 255 : 128)
    }
    expect(new Set(data.map((d) => d.checkpoint.level)).size).toBeGreaterThan(1)
    expect(data.at(-1)?.routeId).toBe('A')
  })
})

describe('checkpointLayer in dark mode', () => {
  it('uses light outlines and stronger faded dots on Dark Matter', () => {
    const layer: ScatterplotLayer<CheckpointDatum> = checkpointLayer(plan.routes, 'A', 'dark')
    const data = layer.props.data as CheckpointDatum[]
    const other = must(data.find((d) => d.routeId !== 'A'))
    const outline = call(layer.props.getLineColor, must(data.at(-1))) as number[]
    expect(outline.slice(0, 3).reduce((sum, c) => sum + c, 0)).toBeGreaterThan(600)
    expect((call(layer.props.getFillColor, other) as number[])[3]).toBeGreaterThan(128)
  })
})

describe('heatmapLayer', () => {
  it('heatmap getWeight reads values[hour][i] and data identity is stable across hours', () => {
    const grid = buildHeatmapGrid(plan.heatmap)
    const at3 = heatmapLayer(grid, 3, 'wind_mph')
    const at10 = heatmapLayer(grid, 10, 'wind_mph')

    expect(at3.props.data).toBe(at10.props.data)
    expect(at3.props.data).toBe(plan.heatmap.points)

    plan.heatmap.points.forEach((point, i) => {
      expect(call(at10.props.getWeight, point, i)).toBeCloseTo(
        must(plan.heatmap.wind_mph[10]?.[i]),
        4,
      )
      expect(call(at3.props.getWeight, point, i)).toBeCloseTo(
        must(plan.heatmap.wind_mph[3]?.[i]),
        4,
      )
    })
    expect(at10.props.updateTriggers.getWeight).toEqual([10, 'wind_mph'])
    expect(at10.props.colorDomain).toEqual([0, 60])
  })

  it('shifts risk levels off zero so Low still draws, onto the color texel centres', () => {
    const grid = buildHeatmapGrid(plan.heatmap)
    const layer = heatmapLayer(grid, 2, 'risk')
    const [low, max] = layer.props.colorDomain as [number, number]
    const stops = METRICS.risk.stops.light
    const texelCentre = (level: number) => (level + 0.5) / stops.length

    plan.heatmap.points.forEach((point, i) => {
      const level = must(plan.heatmap.risk[2]?.[i])
      const weight = call(layer.props.getWeight, point, i) as number
      expect(weight).toBe(level + 0.5)
      expect(weight).toBeGreaterThanOrEqual(low)
      expect(weight / max).toBeCloseTo(texelCentre(level), 6)
    })
    expect(layer.props.colorRange).toBe(stops)
    expect(must(stops[0])[3]).toBe(70)
    expect(must(stops[0]).slice(0, 3)).toEqual([...riskRgb('low')])
    expect(must(METRICS.wind_mph.stops.light[0])[3]).toBe(0)
  })

  it('uses a fixed color domain per metric and hides without rebuilding the grid', () => {
    const grid = buildHeatmapGrid(plan.heatmap)
    expect(heatmapLayer(grid, 0, 'risk').props.colorDomain).toEqual([0.5, 5])
    expect(heatmapLayer(grid, 0, 'precip_in_hr').props.colorDomain).toEqual([0, 1])
    const faded = heatmapLayer(grid, 0, 'risk', { fade: 0 })
    expect(faded.props.visible).toBe(false)
    expect(faded.props.data).toBe(grid.points)
    const hidden = heatmapLayer(grid, 0, 'risk', { visible: false })
    expect(hidden.props.visible).toBe(false)
    expect(hidden.props.data).toBe(grid.points)
  })
})
