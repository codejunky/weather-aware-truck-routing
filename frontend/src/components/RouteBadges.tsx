import BlockIcon from '@mui/icons-material/Block'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import DirectionsCarIcon from '@mui/icons-material/DirectionsCarOutlined'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import type { Route } from '@/api/schemas'

interface RouteBadgesProps {
  route: Pick<Route, 'blocked' | 'truck_profile'>
  recommended?: boolean
}

export function RouteBadges({ route, recommended = false }: RouteBadgesProps) {
  if (!recommended && !route.blocked && route.truck_profile) return null
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
      {recommended ? (
        <Chip size="small" color="primary" icon={<CheckCircleIcon />} label="Recommended" />
      ) : null}
      {route.blocked ? (
        <Chip
          size="small"
          icon={<BlockIcon />}
          label="Blocked"
          sx={{
            bgcolor: 'risk.no_travel.main',
            color: 'risk.no_travel.contrastText',
            '& .MuiChip-icon': { color: 'inherit' },
          }}
        />
      ) : null}
      {!route.truck_profile ? (
        <Chip size="small" variant="outlined" icon={<DirectionsCarIcon />} label="Car route" />
      ) : null}
    </Box>
  )
}
