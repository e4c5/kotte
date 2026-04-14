/**
 * API client for backend communication (fetch-based).
 */

import { apiCache } from '../utils/apiCache'

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

/** Drop cached GET responses affected by graph/query mutations (prefix match on URL path). */
function invalidateCachesAfterMutation(): void {
  apiCache.clear('/graphs')
  apiCache.clear('/queries')
}

interface RequestOptions {
  _csrfRetry?: boolean
  cacheTtl?: number // TTL in milliseconds
}

function getCachedGetResponse<T>(method: Method, url: string, options?: RequestOptions): { data: T } | null {
  if (method !== 'GET' || !options?.cacheTtl) return null
  const cached = apiCache.get<T>(url)
  return cached !== null ? { data: cached } : null
}

async function getCsrfTokenForMethod(method: Method): Promise<string | null> {
  const needsCsrf = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)
  if (!needsCsrf) return null
  return sessionStorage.getItem('csrf_token') || (await ensureCsrfToken())
}

function buildHeaders(csrfToken: string | null): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (csrfToken) headers['X-CSRF-Token'] = csrfToken
  return headers
}

async function parseResponseData(res: Response): Promise<Record<string, unknown>> {
  const text = await res.text()
  return text ? (JSON.parse(text) as Record<string, unknown>) : {}
}

function persistCsrfToken(data: Record<string, unknown>): void {
  if (data.csrf_token != null) {
    sessionStorage.setItem('csrf_token', String(data.csrf_token))
  }
}

function cacheSuccessfulGet<T>(method: Method, url: string, options: RequestOptions | undefined, data: T): void {
  if (method === 'GET' && options?.cacheTtl) {
    apiCache.set(url, data, options.cacheTtl)
  }
}

function invalidateCachesForMutation(method: Method): void {
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    invalidateCachesAfterMutation()
  }
}

function handleUnauthorized(res: Response): void {
  if (res.status !== 401) return
  sessionStorage.removeItem('csrf_token')
  apiCache.clear()
  if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
    window.location.href = '/login'
  }
}

async function retryOnCsrfFailure<T>(
  res: Response,
  apiError: APIError['error'] | undefined,
  method: Method,
  url: string,
  body: unknown,
  options?: RequestOptions
): Promise<{ data: T } | null> {
  const isCsrfFailure = res.status === 403 && apiError?.message === 'CSRF token validation failed'
  if (!isCsrfFailure || options?._csrfRetry) return null

  sessionStorage.removeItem('csrf_token')
  const token = await ensureCsrfToken()
  if (!token) return null
  return request<T>(method, url, body, { ...options, _csrfRetry: true })
}

export async function request<T>(
  method: Method,
  url: string,
  body?: unknown,
  options?: RequestOptions
): Promise<{ data: T }> {
  const cachedResponse = getCachedGetResponse<T>(method, url, options)
  if (cachedResponse) return cachedResponse

  const csrfToken = await getCsrfTokenForMethod(method)
  const headers = buildHeaders(csrfToken)

  const res = await fetch(BASE + url, {
    method,
    credentials: 'include',
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  const data = await parseResponseData(res)

  if (res.ok) {
    persistCsrfToken(data)
    const resultData = data as T
    cacheSuccessfulGet(method, url, options, resultData)
    invalidateCachesForMutation(method)

    return { data: resultData }
  }

  const apiError = (data as unknown as APIError).error
  handleUnauthorized(res)

  const csrfRetry = await retryOnCsrfFailure<T>(res, apiError, method, url, body, options)
  if (csrfRetry) return csrfRetry

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
  get: <T>(url: string, options?: RequestOptions) => request<T>('GET', url, undefined, options),
  post: <T>(url: string, body?: unknown, options?: RequestOptions) => request<T>('POST', url, body, options),
  put: <T>(url: string, body?: unknown, options?: RequestOptions) => request<T>('PUT', url, body, options),
  patch: <T>(url: string, body?: unknown, options?: RequestOptions) => request<T>('PATCH', url, body, options),
  delete: <T>(url: string, options?: RequestOptions) => request<T>('DELETE', url, undefined, options),
}

export default apiClient
