import Box from '@mui/material/Box'
import { visuallyHidden } from '@/lib/a11y'

export function RouteShield({ id, muted = false }: { id: string; muted?: boolean }) {
  return (
    <Box
      component="span"
      sx={{
        display: 'inline-grid',
        placeItems: 'center',
        flexShrink: 0,
        width: 34,
        height: 36,
        pb: '3px',
        borderRadius: '7px 7px 50% 50% / 7px 7px 38% 38%',
        border: 2,
        borderColor: muted ? 'text.secondary' : 'primary.main',
        bgcolor: muted ? 'transparent' : 'primary.main',
        color: muted ? 'text.secondary' : 'primary.contrastText',
        fontFamily: (theme) => theme.typography.h1.fontFamily,
        fontWeight: 700,
        fontSize: '1.25rem',
        lineHeight: 1,
      }}
    >
      <Box component="span" sx={visuallyHidden}>{`Route ${id}`}</Box>
      <span aria-hidden>{id}</span>
    </Box>
  )
}
