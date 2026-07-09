// Client side of cloud sync. The "workspace key" is a passphrase the trainer
// picks; it both authenticates and namespaces their data on the server. Same key
// on any device => same roster. Stored locally so they stay signed in.
import { DB } from './domain'

const WSKEY = 'ridecoach.wskey'
const API = '/api/data'

export const getWsKey = (): string => {
  try { return localStorage.getItem(WSKEY) || '' } catch { return '' }
}
export const setWsKey = (k: string): void => {
  try { k ? localStorage.setItem(WSKEY, k) : localStorage.removeItem(WSKEY) } catch { /* ignore */ }
}
export const cloudEnabled = (): boolean => getWsKey().length >= 8

export async function cloudLoad(): Promise<DB | null> {
  const key = getWsKey()
  if (key.length < 8) return null
  const res = await fetch(API, { headers: { 'x-workspace-key': key } })
  if (!res.ok) throw new Error(`cloud load ${res.status}`)
  const txt = (await res.text()).trim()
  if (!txt) return null
  return JSON.parse(txt) as DB
}

export async function cloudSave(db: DB): Promise<void> {
  const key = getWsKey()
  if (key.length < 8) return
  const res = await fetch(API, {
    method: 'PUT',
    headers: { 'x-workspace-key': key, 'content-type': 'application/json' },
    body: JSON.stringify(db),
  })
  if (!res.ok) throw new Error(`cloud save ${res.status}`)
}
