/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { TripPlanSchema } from './schemas'

const LIVE_PLAN = join(import.meta.dirname, '../../../backend/tests/fixtures/plan_live.json')

describe('backend contract', () => {
  it('parses a response recorded from the live backend', () => {
    const live: unknown = JSON.parse(readFileSync(LIVE_PLAN, 'utf8'))
    const plan = TripPlanSchema.parse(live)
    // zod drops unknown keys, so equality also catches fields the schema does not know about.
    expect(plan).toEqual(live)
    expect(plan.routes.some((r) => r.id === plan.recommended_route_id)).toBe(true)
    expect(plan.heatmap.risk).toHaveLength(49)
  })
})
