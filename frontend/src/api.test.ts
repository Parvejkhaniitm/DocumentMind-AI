// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './api'

const tokenPair = {
  access_token: 'access-old',
  refresh_token: 'refresh-old',
  token_type: 'bearer' as const,
  expires_in: 900,
}

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  api.clearSession()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('DocuMind API client', () => {
  it('stores login tokens and sends the access token with authenticated requests', async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(tokenPair))
      .mockResolvedValueOnce(jsonResponse({ id: 'user-1', display_name: 'Asha' }))
    vi.stubGlobal('fetch', fetchMock)

    await api.login('asha@example.com', 'a-secure-password')
    const user = await api.me()

    expect(api.hasSession()).toBe(true)
    expect(user.display_name).toBe('Asha')
    expect(fetchMock.mock.calls[1][1]?.headers).toBeInstanceOf(Headers)
    expect(new Headers(fetchMock.mock.calls[1][1]?.headers).get('Authorization')).toBe(
      'Bearer access-old',
    )
  })

  it('refreshes an expired access token and retries the original request', async () => {
    const freshTokens = { ...tokenPair, access_token: 'access-new', refresh_token: 'refresh-new' }
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(tokenPair))
      .mockResolvedValueOnce(jsonResponse({ detail: 'Expired' }, 401))
      .mockResolvedValueOnce(jsonResponse(freshTokens))
      .mockResolvedValueOnce(jsonResponse({ id: 'user-1', display_name: 'Asha' }))
    vi.stubGlobal('fetch', fetchMock)

    await api.login('asha@example.com', 'a-secure-password')
    const user = await api.me()

    expect(user.id).toBe('user-1')
    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(new Headers(fetchMock.mock.calls[3][1]?.headers).get('Authorization')).toBe(
      'Bearer access-new',
    )
    expect(api.hasSession()).toBe(true)
  })

  it('reports structured API errors with their HTTP status', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValueOnce(
      jsonResponse({ error: { message: 'Workspace access required.' } }, 403),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.listWorkspaces()).rejects.toMatchObject<ApiError>({
      name: 'ApiError',
      message: 'Workspace access required.',
      status: 403,
    })
  })
})
