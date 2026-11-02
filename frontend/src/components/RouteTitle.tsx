import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import type { Route } from '@/api/schemas'
import { RouteShield } from './RouteShield'

interface RouteTitleProps {
  route: Route
  id?: string
  heading?: boolean
}

export function RouteTitle({ route, id, heading = false }: RouteTitleProps) {
  return (
    <Typography
      id={id}
      component={heading ? 'h3' : 'p'}
      variant={heading ? 'h4' : 'h5'}
      sx={{ display: 'flex', alignItems: 'center', gap: heading ? 1.25 : 1, flex: 1, minWidth: 0 }}
    >
      <RouteShield id={route.id} muted={route.blocked} />
      <Box component="span" sx={{ overflowWrap: 'anywhere' }}>
        {route.summary}
      </Box>
    </Typography>
  )
}
