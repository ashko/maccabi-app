// Client side of cloud sync. The "workspace key" is a passphrase the trainer
// picks; it both authenticates and namespaces their data on the server. Same key
// on any device => same roster. Stored locally so they stay signed in.
import { DB, migrateDB } from './domain'

const WSKEY = 'ridecoach.wskey'
const API = '/api/data'

export const getWsKey = (): string => {
  try { return localStorage.getItem(WSKEY) || '' } catch { return '' }
}
export const setWsKey = (k: string): void => {
  try { k ? localStorage.setItem(WSKEY, k) : localStorage.removeItem(WSKEY) } catch { /* ignore */ }
}
export const cloudEnabled = (): boolean => getWsKey().length >= 8

async function detail(res: Response): Promise<string> {
  const body = await res.text().catch(() => '')
  let msg = body
  try { msg = JSON.parse(body).error || body } catch { /* keep raw */ }
  if (res.status === 501) return 'הענן לא מחובר (501) — ודא ש-KV מחובר ושבוצע Redeploy'
  return `שגיאה ${res.status}${msg ? ` — ${msg}` : ''}`
}

export async function cloudLoad(): Promise<DB | null> {
  const key = getWsKey()
  if (key.length < 8) return null
  const res = await fetch(API, { headers: { 'x-workspace-key': key }, cache: 'no-store' })
  if (!res.ok) throw new Error(await detail(res))
  const txt = (await res.text()).trim()
  if (!txt || txt === 'null') return null
  try { return migrateDB(JSON.parse(txt) as DB) } catch { return null }
}

export async function cloudSave(db: DB): Promise<void> {
  const key = getWsKey()
  if (key.length < 8) return
  const res = await fetch(API, {
    method: 'PUT',
    headers: { 'x-workspace-key': key, 'content-type': 'application/json' },
    cache: 'no-store',
    body: JSON.stringify(db),
  })
  if (!res.ok) throw new Error(await detail(res))
}
