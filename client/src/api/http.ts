const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message?: string,
  ) {
    super(message ?? `HTTP ${status}`)
    this.name = 'HttpError'
  }
}

type HttpInit = Omit<RequestInit, 'body'> & {
  body?: unknown
  token?: string | null
}

function describeError(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
  }
  return `HTTP ${status}`
}

export async function http<T = unknown>(path: string, init: HttpInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined) headers.set('Content-Type', 'application/json')
  if (init.token) headers.set('Authorization', `Bearer ${init.token}`)

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  })

  const text = await res.text()
  const body: unknown = text ? JSON.parse(text) : null

  if (!res.ok) {
    throw new HttpError(res.status, body, describeError(body, res.status))
  }
  return body as T
}
