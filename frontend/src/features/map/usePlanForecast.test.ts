import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { TripPlanSchema, type TripPlan } from '@/api/schemas'
import fixture from '@/test/fixtures/plan.json'
import { usePlanForecast } from './usePlanForecast'

const plan = TripPlanSchema.parse(fixture)
const initialProps: { plan: TripPlan | null } = { plan }

describe('usePlanForecast', () => {
  it('resets the hour to 0 on a new plan but keeps it across re-renders', () => {
    const { result, rerender } = renderHook(
      (p: { plan: TripPlan | null }) => usePlanForecast(p.plan),
      {
        initialProps,
      },
    )
    act(() => {
      result.current.setHour(17)
    })
    rerender({ plan })
    expect(result.current.hour).toBe(17)
    const key = result.current.planKey

    rerender({ plan: { ...plan } })
    expect(result.current.hour).toBe(0)
    expect(result.current.planKey).toBe(key + 1)
  })

  it('derives the max hour from the heatmap, falling back to 48', () => {
    const { result, rerender } = renderHook(
      (p: { plan: TripPlan | null }) => usePlanForecast(p.plan),
      {
        initialProps,
      },
    )
    expect(result.current.maxHour).toBe(plan.heatmap.risk.length - 1)
    rerender({ plan: null })
    expect(result.current.maxHour).toBe(48)
  })
})
