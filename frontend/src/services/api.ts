/**
 * API client for backend communication (fetch-based).
 */

const BASE = '/api/v1'

export interface APIError {
  error: {
    code: string
    category: string
    message: string
    details?: Record<string, unknown>
    request_id: string
    timestamp: string
    retryable: boolean
  }
}

export class APIErrorException extends Error {
  constructor(
    public code: string,
    public category: string,
    message: string,
    public details?: Record<string, unknown>,
    public requestId?: string,
    public retryable: boolean = false
  ) {
    super(message)
    this.name = 'APIErrorException'
  }
}

/** Fetch and store CSRF token. Exported for use by fetch-based APIs (e.g. stream). */
export async function ensureCsrfToken(): Promise<string | null> {
  let token = sessionStorage.getItem('csrf_token')
  if (token) return token
  try {
    const res = await fetch(`${BASE}/auth/csrf-token`, { credentials: 'include' })
    const data = await res.json().catch(() => ({}))
    token = data?.csrf_token ?? null
    if (token) sessionStorage.setItem('csrf_token', token)
    return token
  } catch {
    return null
  }
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface RequestOptions {
  _csrfRetry?: boolean
}

async function request<T>(
  method: Method,
  url: string,
  body?: unknown,
  options?: RequestOptions
): Promise<{ data: T }> {
  const needsCsrf = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)
  let csrfToken: string | null = null
  if (needsCsrf) {
    csrfToken = sessionStorage.getItem('csrf_token') || (await ensureCsrfToken())
  }

  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (csrfToken) headers['X-CSRF-Token'] = csrfToken

  const res = await fetch(BASE + url, {
    method,
    credentials: 'include',
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  const text = await res.text()
  const data = text ? (JSON.parse(text) as Record<string, unknown>) : {}

  if (res.ok) {
    if (data.csrf_token != null) {
      sessionStorage.setItem('csrf_token', String(data.csrf_token))
    }
    return { data: data as T }
  }

  const apiError = (data as unknown as APIError).error

  if (res.status === 401) {
    sessionStorage.removeItem('csrf_token')
    if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
      window.location.href = '/login'
    }
  }

  const isCsrfFailure =
    res.status === 403 && apiError?.message === 'CSRF token validation failed'
  if (isCsrfFailure && !options?._csrfRetry) {
    const token = await ensureCsrfToken()
    if (token) {
      return request<T>(method, url, body, { _csrfRetry: true })
    }
  }

  if (apiError) {
    throw new APIErrorException(
      apiError.code,
      apiError.category,
      apiError.message,
      apiError.details,
      apiError.request_id,
      apiError.retryable
    )
  }
  throw new Error((data?.message as string) || res.statusText || 'Request failed')
}

const apiClient = {
  get: <T>(url: string) => request<T>('GET', url),
  post: <T>(url: string, body?: unknown) => request<T>('POST', url, body),
  put: <T>(url: string, body?: unknown) => request<T>('PUT', url, body),
  patch: <T>(url: string, body?: unknown) => request<T>('PATCH', url, body),
  delete: <T>(url: string) => request<T>('DELETE', url),
}

export default apiClient
