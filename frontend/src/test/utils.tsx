import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@mui/material/styles'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { vi } from 'vitest'
import { theme } from '@/theme'

export function renderWithProviders(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider theme={theme}>{ui}</ThemeProvider>
    </QueryClientProvider>,
  )
}

export function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

export function urlOf(input: RequestInfo | URL) {
  return input instanceof Request ? input.url : input.toString()
}

type Handler = (url: string, init?: RequestInit) => Response

export function mockFetch(handler: Handler) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    return Promise.resolve(handler(urlOf(input), init))
  })
}

export const PLACES = {
  chicago: { label: 'Chicago, IL', lat: 41.8781, lon: -87.6298 },
  denver: { label: 'Denver, CO', lat: 39.7392, lon: -104.9903 },
}

export function geocodeResponse(url: string) {
  const q = new URL(url, 'http://localhost').searchParams.get('q')?.toLowerCase() ?? ''
  const results = Object.values(PLACES).filter((p) => p.label.toLowerCase().startsWith(q))
  return jsonResponse(200, { results })
}
