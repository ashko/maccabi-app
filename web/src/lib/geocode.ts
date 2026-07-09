// Free address autocomplete via Photon (Komoot) — no API key, CORS-enabled.
// Returns human-readable labels; coordinates are kept internally for routing.
import { Loc } from './domain'

const ENDPOINT = 'https://photon.komoot.io/api/'
// bias results toward the Tel Aviv area
const BIAS = { lat: 32.08, lon: 34.78 }

function label(p: Record<string, any>): string {
  const parts = [
    [p.name, p.housenumber].filter(Boolean).join(' '),
    p.street && p.street !== p.name ? p.street : '',
    p.city || p.town || p.village || p.district,
  ].filter(Boolean)
  // de-dup consecutive equal parts
  return parts.filter((v, i) => v && v !== parts[i - 1]).join(', ')
}

export async function searchAddress(query: string, signal?: AbortSignal): Promise<Loc[]> {
  const q = query.trim()
  if (q.length < 2) return []
  const url = `${ENDPOINT}?q=${encodeURIComponent(q)}&limit=6&lang=default&lat=${BIAS.lat}&lon=${BIAS.lon}`
  const res = await fetch(url, { signal })
  if (!res.ok) throw new Error(`geocode ${res.status}`)
  const data = await res.json()
  return (data.features || []).map((f: any) => ({
    name: label(f.properties) || q,
    lat: f.geometry.coordinates[1],
    lng: f.geometry.coordinates[0],
  }))
}
