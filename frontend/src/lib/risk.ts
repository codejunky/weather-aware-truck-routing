export const RISK_LEVELS = ['low', 'moderate', 'high', 'severe', 'no_travel'] as const

export type RiskLevel = (typeof RISK_LEVELS)[number]

export interface RiskColor {
  main: string
  contrastText: string
}

export const INK = '#14202B'
export const INK_ON_DARK = '#E8EDF2'
export const WHITE = '#FFFFFF'

export const RISK_COLORS = {
  low: { main: '#1A7A6D', contrastText: WHITE },
  moderate: { main: '#F2C94C', contrastText: INK },
  high: { main: '#F08A3C', contrastText: INK },
  severe: { main: '#C42B47', contrastText: WHITE },
  no_travel: { main: '#5B2182', contrastText: WHITE },
} as const satisfies Record<RiskLevel, RiskColor>

const LABELS: Record<RiskLevel, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  severe: 'Severe',
  no_travel: 'No travel',
}

export type Rgb = readonly [number, number, number]

export function hexToRgb(hex: string): Rgb {
  const channel = (offset: number) => parseInt(hex.slice(offset, offset + 2), 16)
  return [channel(1), channel(3), channel(5)]
}

const RGB: Record<RiskLevel, Rgb> = {
  low: hexToRgb(RISK_COLORS.low.main),
  moderate: hexToRgb(RISK_COLORS.moderate.main),
  high: hexToRgb(RISK_COLORS.high.main),
  severe: hexToRgb(RISK_COLORS.severe.main),
  no_travel: hexToRgb(RISK_COLORS.no_travel.main),
}

export function rgbaCss([r, g, b]: Rgb, alpha: number): string {
  return `rgb(${r} ${g} ${b} / ${alpha})`
}

export function riskRgb(level: RiskLevel): Rgb {
  return RGB[level]
}

export function riskLabel(level: RiskLevel): string {
  return LABELS[level]
}
