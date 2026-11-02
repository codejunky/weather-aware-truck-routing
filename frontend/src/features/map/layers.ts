import { HeatmapLayer } from '@deck.gl/aggregation-layers'
import { PathLayer, ScatterplotLayer } from '@deck.gl/layers'
import polyline from '@mapbox/polyline'
import type { Checkpoint, HeatmapMetric, Route, TripPlan } from '@/api/schemas'
import { hexToRgb, INK, INK_ON_DARK, RISK_COLORS, RISK_LEVELS, riskRgb, WHITE } from '@/lib/risk'
import { ACCENT } from '@/theme'

export type Scheme = 'light' | 'dark'
type Rgba = [number, number, number, number]
type LngLat = [number, number]

export const LAYER_IDS = {
  heatmap: 'heatmap',
  routes: 'routes',
  routesCasing: 'routes-casing',
  selectedRoute: 'route-selected',
  selectedRouteCasing: 'route-selected-casing',
  checkpoints: 'checkpoints',
  endpoints: 'endpoints',
} as const

const ROUTE_LAYER_IDS: ReadonlySet<string> = new Set([
  LAYER_IDS.routes,
  LAYER_IDS.routesCasing,
  LAYER_IDS.selectedRoute,
  LAYER_IDS.selectedRouteCasing,
])

export interface DecodedRoute {
  id: string
  path: LngLat[]
}

export interface CheckpointDatum {
  routeId: string
  selected: boolean
  checkpoint: Checkpoint
}

export interface HeatmapGrid {
  points: LngLat[]
  values: Record<HeatmapMetric, Float32Array>
}

type Heatmap = TripPlan['heatmap']

const rgba = (hex: string, alpha = 255): Rgba => [...hexToRgb(hex), alpha]

const ROUTE_STYLE = {
  light: { muted: rgba('#7D8B99'), casing: rgba(WHITE, 235), ink: rgba(INK) },
  dark: { muted: rgba('#7E8E9F'), casing: rgba('#0B1118', 235), ink: rgba(INK_ON_DARK) },
} as const

// Dark rings keep yellow dots legible on Positron; Dark Matter needs light rings instead.
const CHECKPOINT_STYLE = {
  light: { outline: rgba(INK, 210), outlineMuted: rgba(INK, 90), fadedAlpha: 128 },
  dark: { outline: rgba(INK_ON_DARK, 200), outlineMuted: rgba(INK_ON_DARK, 80), fadedAlpha: 170 },
} as const

export function decodeRoutes(routes: Route[]): DecodedRoute[] {
  return routes.map((route) => ({
    id: route.id,
    path: polyline.decode(route.polyline, 6).map(([lat, lon]): LngLat => [lon, lat]),
  }))
}

function pathPair(
  [casingId, id]: [string, string],
  data: DecodedRoute[],
  color: Rgba,
  casing: Rgba,
  width: number,
) {
  const common = {
    data,
    getPath: (d: DecodedRoute) => d.path,
    widthUnits: 'pixels' as const,
    capRounded: true,
    jointRounded: true,
    pickable: true,
  }
  return [
    new PathLayer<DecodedRoute>({
      ...common,
      id: casingId,
      getColor: casing,
      getWidth: () => width + 4,
    }),
    new PathLayer<DecodedRoute>({ ...common, id, getColor: color, getWidth: () => width }),
  ]
}

export function routeLayers(routes: DecodedRoute[], selectedId: string | null, scheme: Scheme) {
  const style = ROUTE_STYLE[scheme]
  const others = routes.filter((r) => r.id !== selectedId)
  const selected = routes.filter((r) => r.id === selectedId)
  return [
    ...pathPair([LAYER_IDS.routesCasing, LAYER_IDS.routes], others, style.muted, style.casing, 4),
    ...pathPair(
      [LAYER_IDS.selectedRouteCasing, LAYER_IDS.selectedRoute],
      selected,
      rgba(ACCENT[scheme]),
      style.casing,
      6,
    ),
  ]
}

export function checkpointLayer(
  routes: Route[],
  selectedId: string | null,
  scheme: Scheme = 'light',
) {
  const style = CHECKPOINT_STYLE[scheme]
  const data: CheckpointDatum[] = routes
    .flatMap((route) =>
      route.checkpoints.map((checkpoint) => ({
        routeId: route.id,
        selected: route.id === selectedId,
        checkpoint,
      })),
    )
    .sort((a, b) => Number(a.selected) - Number(b.selected))

  return new ScatterplotLayer<CheckpointDatum>({
    id: LAYER_IDS.checkpoints,
    data,
    getPosition: (d) => [d.checkpoint.lon, d.checkpoint.lat],
    getFillColor: (d) => [...riskRgb(d.checkpoint.level), d.selected ? 255 : style.fadedAlpha],
    getLineColor: (d) => (d.selected ? style.outline : style.outlineMuted),
    getRadius: (d) => (d.selected ? 5 : 3.5),
    radiusUnits: 'pixels',
    lineWidthUnits: 'pixels',
    getLineWidth: (d) => (d.selected ? 1.5 : 1),
    stroked: true,
    pickable: true,
  })
}

export function endpointLayer(route: DecodedRoute | undefined, scheme: Scheme) {
  const first = route?.path[0]
  const last = route?.path.at(-1)
  const ends =
    first && last
      ? [
          { position: first, end: 0 },
          { position: last, end: 1 },
        ]
      : []
  const { ink, casing } = ROUTE_STYLE[scheme]
  return new ScatterplotLayer<{ position: LngLat; end: number }>({
    id: LAYER_IDS.endpoints,
    data: ends,
    getPosition: (d) => d.position,
    getFillColor: (d) => (d.end === 0 ? casing : ink),
    getLineColor: (d) => (d.end === 0 ? ink : casing),
    getRadius: 9,
    getLineWidth: 3,
    radiusUnits: 'pixels',
    lineWidthUnits: 'pixels',
    stroked: true,
  })
}

interface MetricSpec {
  label: string
  unit: string
  domain: [number, number]
  stops: Record<Scheme, Rgba[]>
  ticks: number[]
}

const ramp = (hexes: string[], firstAlpha = 0): Rgba[] =>
  hexes.map((hex, i) =>
    rgba(hex, i === 0 ? firstAlpha : Math.round(110 + (i / (hexes.length - 1)) * 120)),
  )

const riskRamp = ramp(
  RISK_LEVELS.map((level) => RISK_COLORS[level].main),
  70,
)

export const METRICS: Record<HeatmapMetric, MetricSpec> = {
  risk: {
    label: 'Risk',
    unit: '',
    domain: [0.5, 5],
    stops: { light: riskRamp, dark: riskRamp },
    ticks: [0, 1, 2, 3, 4],
  },
  wind_mph: {
    label: 'Wind',
    unit: 'mph',
    domain: [0, 60],
    stops: {
      light: ramp(['#E4DEF7', '#BBA8E6', '#8B67CF', '#6236B0', '#3D1680']),
      dark: ramp(['#4A2F8A', '#6A47B8', '#9071D8', '#B9A0F0', '#E4D8FF']),
    },
    ticks: [0, 15, 30, 45, 60],
  },
  precip_in_hr: {
    label: 'Precip',
    unit: 'in/hr',
    domain: [0, 1],
    stops: {
      light: ramp(['#D3E6F5', '#93C2E8', '#4F95D3', '#2167B0', '#0D3F7A']),
      dark: ramp(['#173F6B', '#2766A6', '#4A90D0', '#83BAEA', '#C6E2FA']),
    },
    ticks: [0, 0.25, 0.5, 0.75, 1],
  },
}

export function buildHeatmapGrid(heatmap: Heatmap): HeatmapGrid {
  const n = heatmap.points.length
  const flatten = (rows: number[][], shift = 0) => {
    const out = new Float32Array(rows.length * n)
    rows.forEach((row, h) => {
      out.set(shift ? row.map((v) => v + shift) : row, h * n)
    })
    return out
  }
  return {
    points: heatmap.points,
    values: {
      // deck's heatmap shader discards weights <= 0, so Low (0) would never draw
      risk: flatten(heatmap.risk, 0.5),
      wind_mph: flatten(heatmap.wind_mph),
      precip_in_hr: flatten(heatmap.precip_in_hr),
    },
  }
}

export function heatmapLayer(
  grid: HeatmapGrid,
  hour: number,
  metric: HeatmapMetric,
  {
    visible = true,
    radiusPixels = 40,
    scheme = 'light',
    fade = 1,
  }: { visible?: boolean; radiusPixels?: number; scheme?: Scheme; fade?: number } = {},
) {
  const values = grid.values[metric]
  const offset = hour * grid.points.length
  const spec = METRICS[metric]
  return new HeatmapLayer<LngLat>({
    id: LAYER_IDS.heatmap,
    data: grid.points,
    visible: visible && fade > 0,
    getPosition: (d) => d,
    getWeight: (_, { index }) => values[offset + index] ?? 0,
    updateTriggers: { getWeight: [hour, metric] },
    aggregation: 'MEAN',
    colorDomain: spec.domain,
    colorRange: spec.stops[scheme],
    radiusPixels,
    weightsTextureSize: 512,
    opacity: 0.85 * fade,
  })
}

const MILE_M = 1609.344

// Kernel wide enough that the ±20 mi corridor offsets merge into one band.
export function heatmapRadiusPixels(zoom: number, latitude: number, gridDeg = 0.25) {
  const radiusM = Math.max(75 * MILE_M, gridDeg * 111_320 * 1.5)
  const metersPerPixel = (78_271.52 * Math.cos((latitude * Math.PI) / 180)) / 2 ** zoom
  return Math.min(100, Math.max(12, radiusM / metersPerPixel))
}

export function pathBounds(points: LngLat[]): [LngLat, LngLat] {
  let [minLon, minLat, maxLon, maxLat] = [180, 90, -180, -90]
  for (const [lon, lat] of points) {
    minLon = Math.min(minLon, lon)
    minLat = Math.min(minLat, lat)
    maxLon = Math.max(maxLon, lon)
    maxLat = Math.max(maxLat, lat)
  }
  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ]
}

// The kernel tops out at 100 px, so past ~z6.5 the corridor breaks into blobs; fade it out instead.
export function heatmapFade(zoom: number) {
  return Math.min(1, Math.max(0, (8 - zoom) / 1.5))
}

export type MapTarget =
  { kind: 'checkpoint'; datum: CheckpointDatum } | { kind: 'route'; routeId: string }

const isCheckpointDatum = (o: unknown): o is CheckpointDatum =>
  typeof o === 'object' && o !== null && 'checkpoint' in o && 'routeId' in o

const isDecodedRoute = (o: unknown): o is DecodedRoute =>
  typeof o === 'object' && o !== null && 'path' in o && 'id' in o

export function targetFromPick(info: {
  layer?: { id: string } | null
  object?: unknown
}): MapTarget | null {
  const id = info.layer?.id
  if (id === LAYER_IDS.checkpoints && isCheckpointDatum(info.object)) {
    return { kind: 'checkpoint', datum: info.object }
  }
  if (id !== undefined && ROUTE_LAYER_IDS.has(id) && isDecodedRoute(info.object)) {
    return { kind: 'route', routeId: info.object.id }
  }
  return null
}

export function targetRouteId(target: MapTarget) {
  return target.kind === 'route' ? target.routeId : target.datum.routeId
}
