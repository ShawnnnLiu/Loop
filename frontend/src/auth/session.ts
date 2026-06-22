import { LOGIN_URL } from '../api/client'

/** Send the browser into the server-side Google OAuth flow. */
export function login(): void {
  window.location.assign(LOGIN_URL)
}

/** Clear the session server-side, then return to the entry route. The backend
 *  owns the session cookie, so logout is a real request, not just client state. */
export async function logout(): Promise<void> {
  await fetch('/auth/logout', { method: 'POST', credentials: 'include' })
  window.location.assign('/')
}
