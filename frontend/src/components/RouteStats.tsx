import Box from '@mui/material/Box'
import type { Route } from '@/api/schemas'
import { formatDuration, formatEtaParts, formatMiles } from '@/lib/format'
import { RiskBar } from './RiskBar'
import { Stat } from './Stat'

export function RouteStats({ route, spread = false }: { route: Route; spread?: boolean }) {
  const arrival = formatEtaParts(route.arrival_at)
  return (
    <>
      <Box
        component="dl"
        sx={{
          m: 0,
          display: 'grid',
          gridTemplateColumns: 'repeat(3, auto)',
          justifyContent: spread ? 'space-between' : 'normal',
          gap: spread ? 1 : 1.5,
        }}
      >
        <Stat label="Distance" value={formatMiles(route.distance_mi)} />
        <Stat label="Drive time" value={formatDuration(route.duration_s)} />
        <Stat label="Arrives" value={arrival.time} unit={arrival.zone} />
      </Box>
      <RiskBar risk={route.risk} />
    </>
  )
}
