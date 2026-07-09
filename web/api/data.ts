// Cloud storage endpoint (Vercel serverless function) backed by Vercel KV.
// The trainer's whole database is stored as one JSON blob, namespaced by a hash
// of their private "workspace key". GET loads it, PUT saves it. Same key on
// another device => same data.
//
// If Vercel KV isn't connected yet (no env vars), the endpoint returns 501 and
// the app simply keeps working locally — cloud sync is opt-in.

import type { VercelRequest, VercelResponse } from '@vercel/node'
import { createHash } from 'node:crypto'
import { createClient } from '@vercel/kv'

const MAX_BYTES = 512 * 1024
const MIN_KEY = 8

// Accept whichever names the connected store injects (classic Vercel KV or the
// newer Upstash Redis marketplace integration).
const KV_URL = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL || ''
const KV_TOKEN = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN || ''
const isConfigured = () => !!(KV_URL && KV_TOKEN)

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const key = (req.headers['x-workspace-key'] as string) || ''
  if (key.length < MIN_KEY) return res.status(400).json({ error: 'workspace key too short' })
  if (!isConfigured()) return res.status(501).json({ error: 'cloud storage not configured' })

  const kv = createClient({ url: KV_URL, token: KV_TOKEN })
  const id = 'ridecoach:' + createHash('sha256').update('ridecoach:' + key).digest('hex')

  try {
    if (req.method === 'GET') {
      const data = await kv.get(id) // object or null (KV auto-deserialises)
      res.setHeader('cache-control', 'no-store')
      return res.status(200).json(data ?? null)
    }
    if (req.method === 'PUT' || req.method === 'POST') {
      const obj = typeof req.body === 'string' ? JSON.parse(req.body) : req.body
      if (JSON.stringify(obj).length > MAX_BYTES) return res.status(413).json({ error: 'payload too large' })
      await kv.set(id, obj)
      return res.status(200).json({ ok: true })
    }
    return res.status(405).json({ error: 'method not allowed' })
  } catch (e: any) {
    return res.status(500).json({ error: String(e?.message || e) })
  }
}
