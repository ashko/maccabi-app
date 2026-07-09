// Cloud storage endpoint backed by Netlify Blobs (free, no external account).
// The trainer's whole database is stored as a single JSON blob, namespaced by a
// hash of their private "workspace key" (a passphrase they choose). GET loads it,
// PUT saves it. Same key on another device => same data.

import { getStore } from '@netlify/blobs'
import type { Config } from '@netlify/functions'

const MAX_BYTES = 512 * 1024
const MIN_KEY = 8

async function namespace(key: string): Promise<string> {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode('ridecoach:' + key))
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('')
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } })

export default async (req: Request): Promise<Response> => {
  const key = req.headers.get('x-workspace-key') || ''
  if (key.length < MIN_KEY) return json({ error: 'workspace key too short' }, 400)

  const id = await namespace(key)
  const store = getStore({ name: 'ridecoach', consistency: 'strong' })

  if (req.method === 'GET') {
    const data = (await store.get(id, { type: 'text' })) ?? ''
    return new Response(data, { status: 200, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } })
  }

  if (req.method === 'PUT' || req.method === 'POST') {
    const body = await req.text()
    if (body.length > MAX_BYTES) return json({ error: 'payload too large' }, 413)
    await store.set(id, body)
    return json({ ok: true })
  }

  return json({ error: 'method not allowed' }, 405)
}

export const config: Config = { path: '/api/data' }
