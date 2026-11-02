import { useState } from 'react'
import type { HeatmapMetric, TripPlan } from '@/api/schemas'

const DEFAULT_MAX_HOUR = 48

// Forecast hour and metric are scoped to the current plan; a new plan starts at +0h.
// `planKey` bumps on every new plan so plan-bound children can remount.
export function usePlanForecast(plan: TripPlan | null) {
  const [hour, setHour] = useState(0)
  const [metric, setMetric] = useState<HeatmapMetric>('risk')
  const [seenPlan, setSeenPlan] = useState(plan)
  const [planKey, setPlanKey] = useState(0)

  if (plan !== seenPlan) {
    setSeenPlan(plan)
    setHour(0)
    setPlanKey((k) => k + 1)
  }

  const hours = plan?.heatmap.risk.length ?? 0
  const maxHour = hours > 1 ? hours - 1 : DEFAULT_MAX_HOUR

  return { hour, setHour, metric, setMetric, maxHour, planKey }
}
