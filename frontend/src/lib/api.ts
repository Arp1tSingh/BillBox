import { config } from './config'
import { requireSupabase } from './supabase'

interface ErrorEnvelope {
  error?: {
    code?: string
    message?: string
    details?: Record<string, unknown>
  }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  formData?: FormData
  headers?: Record<string, string>
  householdId?: string
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: ErrorEnvelope = {}
  try {
    body = (await response.json()) as ErrorEnvelope
  } catch {
    // Non-JSON proxy errors still get a useful status-based message.
  }
  return new ApiError(
    response.status,
    body.error?.code ?? `http_${response.status}`,
    body.error?.message ?? 'Something went wrong. Try again.',
    body.error?.details ?? {},
  )
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const client = requireSupabase()
  const {
    data: { session },
  } = await client.auth.getSession()
  if (!session?.access_token) {
    throw new ApiError(401, 'unauthorized', 'Sign in to continue.')
  }

  const send = (accessToken: string) =>
    fetch(`${config.apiBaseUrl}${path}`, {
      method: options.method ?? 'GET',
      headers: {
        ...(options.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
        Authorization: `Bearer ${accessToken}`,
        ...(options.householdId ? { 'X-Household-Id': options.householdId } : {}),
      },
      body: options.formData ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
    })

  let response = await send(session.access_token)
  if (response.status === 401) {
    const { data, error } = await client.auth.refreshSession()
    if (!error && data.session?.access_token) {
      response = await send(data.session.access_token)
    }
  }

  if (!response.ok) {
    throw await toApiError(response)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string, householdId?: string) =>
    request<T>(path, { method: 'GET', householdId }),
  post: <T>(path: string, body?: unknown, householdId?: string) =>
    request<T>(path, { method: 'POST', body, householdId }),
  patch: <T>(path: string, body: unknown, householdId?: string) =>
    request<T>(path, { method: 'PATCH', body, householdId }),
  delete: <T>(path: string, householdId?: string) =>
    request<T>(path, { method: 'DELETE', householdId }),
  upload: <T>(path: string, formData: FormData, householdId?: string) =>
    request<T>(path, { method: 'POST', formData, householdId }),
}
