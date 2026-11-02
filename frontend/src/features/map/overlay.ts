import { hexToRgb, INK, rgbaCss } from '@/lib/risk'

export const OVERLAY_SHADOW = {
  light: rgbaCss(hexToRgb(INK), 0.16),
  dark: rgbaCss([0, 0, 0], 0.5),
} as const
