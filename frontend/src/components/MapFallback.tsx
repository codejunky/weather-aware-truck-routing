import Box from '@mui/material/Box'
import Skeleton from '@mui/material/Skeleton'
import Typography from '@mui/material/Typography'

export function MapFallback() {
  return (
    <Box
      role="status"
      sx={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}
    >
      <Skeleton
        variant="rectangular"
        animation="wave"
        sx={{ position: 'absolute', inset: 0, height: '100%', transform: 'none' }}
      />
      <Typography variant="body2" sx={{ position: 'relative', color: 'text.secondary' }}>
        Loading map…
      </Typography>
    </Box>
  )
}
