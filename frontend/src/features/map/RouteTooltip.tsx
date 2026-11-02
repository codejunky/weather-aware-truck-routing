import Box from '@mui/material/Box'
import type { Route } from '@/api/schemas'
import { RouteBadges } from '@/components/RouteBadges'
import { RouteStats } from '@/components/RouteStats'
import { RouteTitle } from '@/components/RouteTitle'

export function RouteTooltipContent({
  route,
  recommended,
}: {
  route: Route
  recommended: boolean
}) {
  return (
    <Box sx={{ display: 'grid', gap: 1.25 }}>
      <RouteTitle route={route} />
      <RouteBadges route={route} recommended={recommended} />
      <RouteStats route={route} />
    </Box>
  )
}
