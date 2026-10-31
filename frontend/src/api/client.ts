import type {
  Compatibility,
  Fish,
  FishInput,
  Fishtank,
  LoginAnswer,
  Role,
  TankSize,
  User,
} from './types'

const PREFIX = '/fishtank_api'
// The login itself is in a cookie scripts cannot read, the api sets it when logging in.
// This second cookie is readable, its value goes back in CSRF_HEADER with every change, which other sites cannot do
const CSRF_COOKIE = 'fishtank_csrf'
const CSRF_HEADER = 'X-CSRF-Token'
const SAFE_METHODS = ['GET', 'HEAD', 'OPTIONS']

// An error answer of the api, field names the request field that is wrong when the api says so
// retryAfter is the number of seconds to wait when the api answers 429 (too many attempts)
export class ApiError extends Error {
  status: number
  field: string | null
  retryAfter: number | null

  constructor(message: string, status: number, field: string | null = null, retryAfter: number | null = null) {
    super(message)
    this.status = status
    this.field = field
    this.retryAfter = retryAfter
  }
}

// Browser storage can be missing or blocked (private windows), the app then works without remembering
export function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeStorage(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    // nothing to do, the value is just not remembered
  }
}

let onLoginExpired: (() => void) | null = null

// cookies is document.cookie, "a=1; b=2"
export function cookieValue(cookies: string, name: string): string | null {
  for (const part of cookies.split(';')) {
    const [key, ...value] = part.trim().split('=')
    if (key === name) return decodeURIComponent(value.join('='))
  }
  return null
}

function readCookie(name: string): string | null {
  return typeof document === 'undefined' ? null : cookieValue(document.cookie, name)
}

// true while the browser holds a login, the api removes both cookies when it ends
export function hasSession() {
  return readCookie(CSRF_COOKIE) !== null
}

// called when the api refuses the token, the auth context then asks the user to log in again
export function setLoginExpiredHandler(handler: (() => void) | null) {
  onLoginExpired = handler
}

async function request<T>(method: string, path: string, body?: unknown, retried = false): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const csrf = readCookie(CSRF_COOKIE)
  if (csrf && !SAFE_METHODS.includes(method)) headers[CSRF_HEADER] = csrf
  const hadSession = csrf !== null

  let response: Response
  try {
    response = await fetch(PREFIX + path, {
      method,
      headers,
      credentials: 'same-origin',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('Cannot reach the fishtank server, please check your connection', 0)
  }

  const answer = await response.json().catch(() => null)
  if (!response.ok || answer?.status !== 'success') {
    const message = answer?.message ?? `Something went wrong (${response.status})`
    // the api refused the login and removed its cookies
    if (response.status === 401 && hadSession && !hasSession() && path !== '/auth/logout') {
      onLoginExpired?.()
      // reading works as a visitor too, e.g. the catalogue loading at the same time
      if (SAFE_METHODS.includes(method) && !retried && path !== '/auth/me') return request<T>(method, path, body, true)
    }
    const retryAfter = Number(response.headers.get('Retry-After')) || null
    throw new ApiError(message, response.status, answer?.field ?? null, retryAfter)
  }
  return answer as T
}

export const api = {
  register: (username: string, password: string) =>
    request<LoginAnswer>('POST', '/auth/register', { username, password }),
  login: (username: string, password: string) =>
    request<LoginAnswer>('POST', '/auth/login', { username, password }),
  logout: () => request<unknown>('POST', '/auth/logout'),
  me: () => request<{ user: User }>('GET', '/auth/me').then((answer) => answer.user),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<{ user: User }>('POST', '/auth/password', {
      current_password: currentPassword,
      new_password: newPassword,
    }).then((answer) => answer.user),
  deleteAccount: (password: string) => request<unknown>('DELETE', '/auth/me', { password }),

  listFish: (includeRetired = false) =>
    request<{ fish: Fish[] }>('GET', includeRetired ? '/fish?include_retired=true' : '/fish').then(
      (answer) => answer.fish,
    ),
  getFish: (id: number) => request<{ fish: Fish }>('GET', `/fish/${id}`).then((answer) => answer.fish),
  createFish: (fish: FishInput) => request<{ fish: Fish }>('POST', '/fish', fish).then((answer) => answer.fish),
  updateFish: (id: number, fish: FishInput) =>
    request<{ fish: Fish }>('PATCH', `/fish/${id}`, fish).then((answer) => answer.fish),
  deleteFish: (id: number) => request<unknown>('DELETE', `/fish/${id}`),
  retireFish: (id: number) => request<{ fish: Fish }>('POST', `/fish/${id}/retire`).then((answer) => answer.fish),
  restoreFish: (id: number) => request<{ fish: Fish }>('POST', `/fish/${id}/restore`).then((answer) => answer.fish),

  createTank: (options: { name?: string; size?: TankSize } = {}) =>
    request<{ fishtank: Fishtank }>('POST', '/fishtanks', options).then((answer) => answer.fishtank),
  listTanks: () => request<{ fishtanks: Fishtank[] }>('GET', '/fishtanks').then((answer) => answer.fishtanks),
  getTank: (key: string) =>
    request<{ fishtank: Fishtank }>('GET', `/fishtanks/${encodeURIComponent(key)}`).then((answer) => answer.fishtank),
  updateTank: (key: string, changes: { name?: string | null; size?: TankSize }) =>
    request<{ fishtank: Fishtank }>('PATCH', `/fishtanks/${encodeURIComponent(key)}`, changes).then(
      (answer) => answer.fishtank,
    ),
  deleteTank: (key: string) => request<unknown>('DELETE', `/fishtanks/${encodeURIComponent(key)}`),
  saveTank: (key: string) =>
    request<{ fishtank: Fishtank }>('POST', `/fishtanks/${encodeURIComponent(key)}/save`).then(
      (answer) => answer.fishtank,
    ),
  addFish: (key: string, fish: number[]) =>
    request<{ fishtank: Fishtank }>('POST', `/fishtanks/${encodeURIComponent(key)}/add`, { fish }).then(
      (answer) => answer.fishtank,
    ),
  removeFish: (key: string, fish: number[]) =>
    request<{ fishtank: Fishtank }>('POST', `/fishtanks/${encodeURIComponent(key)}/remove`, { fish }).then(
      (answer) => answer.fishtank,
    ),
  compatible: (key: string) =>
    request<Compatibility>('GET', `/fishtanks/${encodeURIComponent(key)}/compatible`),

  listUsers: () => request<{ users: User[] }>('GET', '/users').then((answer) => answer.users),
  setRole: (id: number, role: Role) =>
    request<{ user: User }>('PATCH', `/users/${id}`, { role }).then((answer) => answer.user),
}
