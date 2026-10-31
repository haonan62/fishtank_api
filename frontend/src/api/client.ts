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
const TOKEN_KEY = 'fishtank.token'

// An error answer of the api, field names the request field that is wrong when the api says so
export class ApiError extends Error {
  status: number
  field: string | null

  constructor(message: string, status: number, field: string | null = null) {
    super(message)
    this.status = status
    this.field = field
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

let token: string | null = readStorage(TOKEN_KEY)
let onLoginExpired: (() => void) | null = null

export function getToken() {
  return token
}

export function setToken(value: string | null) {
  token = value
  writeStorage(TOKEN_KEY, value)
}

// called when the api refuses the token, the auth context then asks the user to log in again
export function setLoginExpiredHandler(handler: (() => void) | null) {
  onLoginExpired = handler
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(PREFIX + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('Cannot reach the fishtank server, please check your connection', 0)
  }

  const answer = await response.json().catch(() => null)
  if (!response.ok || answer?.status !== 'success') {
    const message = answer?.message ?? `Something went wrong (${response.status})`
    if (response.status === 401 && token) {
      setToken(null)
      onLoginExpired?.()
    }
    throw new ApiError(message, response.status, answer?.field ?? null)
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
