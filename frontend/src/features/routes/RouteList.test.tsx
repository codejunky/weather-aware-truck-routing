import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { TripPlanSchema, type TripPlan } from '@/api/schemas'
import fixture from '@/test/fixtures/plan.json'
import { renderWithProviders } from '@/test/utils'
import { RouteList } from './RouteList'

const plan = TripPlanSchema.parse(fixture)

function Harness({ initial, data = plan }: { initial: string; data?: TripPlan }) {
  const [selected, setSelected] = useState(initial)
  return <RouteList plan={data} selectedRouteId={selected} onSelect={setSelected} />
}

describe('RouteList', () => {
  it('RouteList puts recommended first', () => {
    const shuffled = { ...plan, routes: [...plan.routes].reverse() }
    renderWithProviders(<RouteList plan={shuffled} selectedRouteId="C" onSelect={vi.fn()} />)

    const group = screen.getByRole('radiogroup', { name: 'Route options' })
    const cards = within(group).getAllByRole('radio')
    expect(cards[0]).toHaveAccessibleName(/^Route A\b/)
    const first = within(cards[0] as HTMLElement)
    expect(first.getByText('Recommended')).toBeInTheDocument()
    expect(first.getByText('Fewest high-risk miles (12.5 vs 48.0)')).toBeInTheDocument()
  })

  it('describes each route in one line and flags blocked and car routes', () => {
    renderWithProviders(<RouteList plan={plan} selectedRouteId="A" onSelect={vi.fn()} />)

    const a = screen.getByRole('radio', { name: /^Route A\b/ })
    expect(a).toBeChecked()
    expect(a).toHaveAccessibleDescription(
      /^1,003 miles, 15 hours, arrives .+, 13 high-risk miles, recommended$/,
    )
    expect(within(a).getByText('Selected')).toBeInTheDocument()

    const c = screen.getByRole('radio', { name: /^Route C\b/ })
    expect(within(c).getByText('Blocked')).toBeInTheDocument()
    expect(c).toHaveAccessibleDescription(/18 no-travel miles, blocked$/)
    const b = screen.getByRole('radio', { name: /^Route B\b/ })
    expect(within(b).getByText('Car route')).toBeInTheDocument()
    expect(b).toHaveAccessibleDescription(/car route$/)
  })

  it('selects on click', async () => {
    const onSelect = vi.fn()
    renderWithProviders(<RouteList plan={plan} selectedRouteId="A" onSelect={onSelect} />)
    await userEvent.click(screen.getByRole('radio', { name: /^Route B\b/ }))
    expect(onSelect).toHaveBeenCalledWith('B')
  })

  it('moves selection with arrow keys using a single tab stop', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Harness initial="A" />)
    const radio = (id: string) => screen.getByRole('radio', { name: new RegExp(`^Route ${id}\\b`) })

    expect(radio('A')).toHaveAttribute('tabindex', '0')
    expect(radio('B')).toHaveAttribute('tabindex', '-1')

    await user.tab()
    expect(radio('A')).toHaveFocus()

    await user.keyboard('{ArrowDown}')
    expect(radio('B')).toHaveFocus()
    expect(radio('B')).toBeChecked()
    expect(radio('A')).not.toBeChecked()
    expect(radio('B')).toHaveAttribute('tabindex', '0')

    await user.keyboard('{ArrowUp}{ArrowUp}')
    expect(radio('C')).toHaveFocus()
    expect(radio('C')).toBeChecked()

    await user.keyboard('{Home}')
    expect(radio('A')).toBeChecked()
    await user.keyboard('{End}')
    expect(radio('C')).toBeChecked()
  })

  it('selects the focused card with Enter or Space', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    renderWithProviders(<RouteList plan={plan} selectedRouteId={null} onSelect={onSelect} />)

    await user.tab()
    expect(screen.getByRole('radio', { name: /^Route A\b/ })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(onSelect).toHaveBeenLastCalledWith('A')
    await user.keyboard(' ')
    expect(onSelect).toHaveBeenCalledTimes(2)
  })
})
