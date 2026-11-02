import { z } from 'zod'
import { RISK_LEVELS } from '@/lib/risk'

const RiskLevelSchema = z.enum(RISK_LEVELS)

const PlaceSchema = z.object({
  label: z.string(),
  lat: z.number(),
  lon: z.number(),
})

export const GeocodeResponseSchema = z.object({ results: z.array(PlaceSchema) })

const CheckpointSchema = z.object({
  mile: z.number(),
  lat: z.number(),
  lon: z.number(),
  eta: z.string(),
  level: RiskLevelSchema,
  factors: z.object({ wind: RiskLevelSchema, rain: RiskLevelSchema, snow: RiskLevelSchema }),
  load_adjusted: z.boolean(),
  weather: z.object({
    wind_mph: z.number(),
    gust_mph: z.number(),
    rain_in_hr: z.number(),
    snow_in_hr: z.number(),
  }),
})

const RouteRiskSchema = z.object({
  no_travel_mi: z.number(),
  severe_mi: z.number(),
  high_mi: z.number(),
  moderate_mi: z.number(),
  low_mi: z.number(),
  avg_risk: z.number(),
})

const RouteSchema = z.object({
  id: z.string(),
  summary: z.string(),
  truck_profile: z.boolean(),
  distance_mi: z.number(),
  duration_s: z.number(),
  arrival_at: z.string(),
  polyline: z.string(),
  blocked: z.boolean(),
  rank: z.number().int(),
  risk: RouteRiskSchema,
  reasons: z.array(z.string()),
  checkpoints: z.array(CheckpointSchema),
})

const hourly = z.array(z.array(z.number()))

export const TripPlanSchema = z.object({
  departure_at: z.string(),
  recommended_route_id: z.string(),
  weather_grid_deg: z.number(),
  notices: z.array(z.string()),
  routes: z.array(RouteSchema),
  heatmap: z.object({
    start: z.string(),
    points: z.array(z.tuple([z.number(), z.number()])),
    risk: hourly,
    wind_mph: hourly,
    precip_in_hr: hourly,
  }),
})

export const ApiErrorBodySchema = z.object({
  code: z.string(),
  detail: z.string(),
  fields: z.record(z.string(), z.unknown()).optional(),
})

export const SAMPLE_INTERVALS = [10, 25, 50] as const

export const TripRequestSchema = z.object({
  origin: PlaceSchema,
  destination: PlaceSchema,
  departure_at: z.string(),
  load_weight_lb: z.number().int(),
  sample_interval_mi: z.literal(SAMPLE_INTERVALS),
})

export type Place = z.infer<typeof PlaceSchema>
export type RouteRisk = z.infer<typeof RouteRiskSchema>
export type Route = z.infer<typeof RouteSchema>
export type Checkpoint = z.infer<typeof CheckpointSchema>
export type TripPlan = z.infer<typeof TripPlanSchema>
export type TripRequest = z.infer<typeof TripRequestSchema>
export type SampleInterval = (typeof SAMPLE_INTERVALS)[number]
export type HeatmapMetric = 'risk' | 'wind_mph' | 'precip_in_hr'
