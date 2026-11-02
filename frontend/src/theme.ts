import { createTheme } from '@mui/material/styles'
import { INK, INK_ON_DARK, RISK_COLORS, WHITE, type RiskColor, type RiskLevel } from '@/lib/risk'

declare module '@mui/material/styles' {
  interface Palette {
    risk: Record<RiskLevel, RiskColor>
  }
  interface PaletteOptions {
    risk?: Record<RiskLevel, RiskColor>
  }
}

export const ACCENT = { light: '#2B4FC4', dark: '#8CA5FF' } as const

const display = '"Barlow Condensed", "Arial Narrow", sans-serif'
const body = '"Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif'

export const theme = createTheme({
  cssVariables: true,
  colorSchemes: {
    light: {
      palette: {
        primary: { main: ACCENT.light },
        background: { default: '#F2F5F8', paper: WHITE },
        text: { primary: INK, secondary: '#4A5866' },
        divider: '#D9E0E7',
        risk: RISK_COLORS,
      },
    },
    dark: {
      palette: {
        primary: { main: ACCENT.dark, contrastText: '#0B1220' },
        background: { default: '#0E151D', paper: '#17212C' },
        text: { primary: INK_ON_DARK, secondary: '#9FB0C0' },
        divider: '#2A3745',
        risk: RISK_COLORS,
      },
    },
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: body,
    h1: { fontFamily: display, fontWeight: 700, fontSize: '2.25rem', lineHeight: 1.1 },
    h2: { fontFamily: display, fontWeight: 700, fontSize: '1.75rem', lineHeight: 1.15 },
    h3: { fontFamily: display, fontWeight: 600, fontSize: '1.5rem', lineHeight: 1.2 },
    h4: { fontFamily: display, fontWeight: 600, fontSize: '1.25rem', lineHeight: 1.2 },
    h5: { fontFamily: display, fontWeight: 600, fontSize: '1.125rem', lineHeight: 1.25 },
    h6: {
      fontFamily: display,
      fontWeight: 600,
      fontSize: '1rem',
      lineHeight: 1.3,
      letterSpacing: '0.01em',
    },
    subtitle1: { fontWeight: 600, fontSize: '1rem' },
    subtitle2: { fontWeight: 600, fontSize: '0.875rem' },
    body1: { fontSize: '1rem', lineHeight: 1.5 },
    body2: { fontSize: '0.875rem', lineHeight: 1.5 },
    caption: { fontSize: '0.75rem', lineHeight: 1.4 },
    button: { fontWeight: 600, textTransform: 'none', letterSpacing: 0 },
  },
  components: {
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: { root: { minHeight: 44 } },
    },
    MuiChip: {
      styleOverrides: { root: { fontWeight: 600 } },
    },
    MuiPaper: {
      styleOverrides: { root: { backgroundImage: 'none' } },
    },
  },
})
