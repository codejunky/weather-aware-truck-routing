import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { TripPlanSchema } from '@/api/schemas'
import fixture from '@/test/fixtures/plan.json'
import { renderWithProviders } from '@/test/utils'
import { RouteStats } from './RouteStats'
import { RouteTitle } from './RouteTitle'

const [route] = TripPlanSchema.parse(fixture).routes
if (!route) throw new Error('fixture has no routes')

describe('RouteStats', () => {
  it('lists distance, drive time and arrival, then the risk bar', () => {
    const { container } = renderWithProviders(<RouteStats route={route} />)

    const list = container.querySelector('dl') as HTMLElement
    const terms = within(list)
      .getAllByRole('term')
      .map((t) => t.textContent)
    expect(terms).toEqual(['Distance', 'Drive time', 'Arrives'])
    expect(within(list).getByText('1,003 mi')).toBeInTheDocument()
    expect(within(list).getByText('15h 0m')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /^Miles by risk: / })).toBeInTheDocument()
  })
})

describe('RouteTitle', () => {
  it('names the route by its shield and summary, as a heading when asked', () => {
    renderWithProviders(<RouteTitle route={route} heading />)
    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(
      `Route ${route.id}${route.id}${route.summary}`,
    )
  })
})
