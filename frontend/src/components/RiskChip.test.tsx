import { ThemeProvider } from '@mui/material/styles'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { theme } from '@/theme'
import { RiskChip } from './RiskChip'

describe('RiskChip', () => {
  it('shows the level label on the level color', () => {
    render(
      <ThemeProvider theme={theme}>
        <RiskChip level="no_travel" />
      </ThemeProvider>,
    )
    const label = screen.getByText('No travel')
    expect(label).toBeInTheDocument()
    expect(label.closest('.MuiChip-root')).toHaveStyle({
      backgroundColor: 'rgb(91, 33, 130)',
      color: 'rgb(255, 255, 255)',
    })
  })
})
