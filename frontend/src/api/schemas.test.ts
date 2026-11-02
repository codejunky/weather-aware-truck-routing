import { describe, expect, it } from 'vitest'
import fixture from '@/test/fixtures/plan.json'
import { TripPlanSchema } from './schemas'

describe('TripPlanSchema', () => {
  it('schemas parse fixture', () => {
    const plan = TripPlanSchema.parse(fixture)
    expect(plan.routes).toHaveLength(3)
    expect(plan.routes.find((r) => r.id === plan.recommended_route_id)?.rank).toBe(1)
    expect(plan.heatmap.risk).toHaveLength(49)
    expect(plan.heatmap.wind_mph[0]).toHaveLength(plan.heatmap.points.length)
  })

  it('rejects an unknown risk level', () => {
    const broken = structuredClone(fixture)
    const checkpoint = broken.routes[0]?.checkpoints[0]
    if (checkpoint) checkpoint.level = 'extreme'
    expect(TripPlanSchema.safeParse(broken).success).toBe(false)
  })
})
