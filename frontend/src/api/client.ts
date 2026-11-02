import type { z } from 'zod'
import { ApiErrorBodySchema } from './schemas'

export type FieldMessages = Record<string, string[]>

export class ApiError extends Error {
  readonly code: string
  readonly detail: string
  readonly status: number
  readonly fields?: FieldMessages

  constructor(code: string, detail: string, status: number, fields?: FieldMessages) {
    super(detail)
    this.name = 'ApiError'
    this.code = code
    this.detail = detail
    this.status = status
    this.fields = fields
  }

  get retryable() {
    return this.status === 0 || this.status >= 500 || this.status === 429
  }
}

const isAbort = (error: unknown) => error instanceof DOMException && error.name === 'AbortError'

function messagesOf(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(messagesOf)
  if (value && typeof value === 'object') return Object.values(value).flatMap(messagesOf)
  return []
}

// DRF nests serializer errors ({"origin": {"lat": [...]}}); flatten to dotted keys.
function flattenFields(fields: Record<string, unknown>, prefix = ''): FieldMessages {
  const flat: FieldMessages = {}
  for (const [key, value] of Object.entries(fields)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(flat, flattenFields(value as Record<string, unknown>, path))
    } else {
      const messages = messagesOf(value)
      if (messages.length) flat[path] = messages
    }
  }
  return flat
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch (error) {
    if (isAbort(error)) throw error
    return null
  }
}

async function request<T>(path: string, schema: z.ZodType<T>, init: RequestInit): Promise<T> {
  let response: Response
  try {
    const headers = new Headers(init.headers)
    headers.set('accept', 'application/json')
    response = await fetch(path, { ...init, headers })
  } catch (error) {
    if (isAbort(error)) throw error
    throw new ApiError(
      'network.unreachable',
      'Could not reach the server. Check your connection.',
      0,
    )
  }

  const body = await readJson(response)

  if (!response.ok) {
    const parsed = ApiErrorBodySchema.safeParse(body)
    if (parsed.success) {
      const { code, detail, fields } = parsed.data
      throw new ApiError(code, detail, response.status, fields && flattenFields(fields))
    }
    throw new ApiError(`http.${response.status}`, 'The server returned an error.', response.status)
  }

  const parsed = schema.safeParse(body)
  if (!parsed.success) {
    throw new ApiError(
      'client.bad_response',
      'The server sent a response this app cannot read.',
      response.status,
    )
  }
  return parsed.data
}

export function getJson<T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal) {
  return request(path, schema, { method: 'GET', signal })
}

export function postJson<T>(path: string, body: unknown, schema: z.ZodType<T>) {
  return request(path, schema, {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { 'content-type': 'application/json' },
  })
}
