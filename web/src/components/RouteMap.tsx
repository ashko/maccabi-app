// Live day-route map (Leaflet + free OSM/CARTO tiles, no API key).
// Draws home + the ordered in-person stops, connected by the REAL road route
// (via the free OSRM service). Falls back to straight lines if routing is
// unavailable, so the map always renders something useful.
import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Loc, Scheduled } from '../lib/domain'

interface Props { home: Loc; stops: Scheduled[] }

function tileUrl(): string {
  const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
  return dark
    ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
    : 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png'
}

function marker(kind: 'home' | 'stop', label: string): L.DivIcon {
  const cls = kind === 'home' ? 'mk mk-home' : 'mk mk-stop'
  return L.divIcon({ className: '', html: `<div class="${cls}">${label}</div>`, iconSize: [30, 30], iconAnchor: [15, 15] })
}

// Ask OSRM for the road geometry through the ordered waypoints. Returns
// [lat,lng] points, or null on any failure (caller keeps the straight line).
async function fetchRoad(points: [number, number][], signal: AbortSignal): Promise<[number, number][] | null> {
  if (points.length < 2) return null
  const coords = points.map(([lat, lng]) => `${lng},${lat}`).join(';')
  const url = `https://router.project-osrm.org/route/v1/driving/${coords}?overview=full&geometries=geojson`
  try {
    const res = await fetch(url, { signal })
    if (!res.ok) return null
    const data = await res.json()
    if (data.code !== 'Ok' || !data.routes?.length) return null
    return data.routes[0].geometry.coordinates.map(([lng, lat]: [number, number]) => [lat, lng])
  } catch {
    return null
  }
}

export default function RouteMap({ home, stops }: Props) {
  const elRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerRef = useRef<L.LayerGroup | null>(null)

  useEffect(() => {
    if (!elRef.current || mapRef.current) return
    const map = L.map(elRef.current, { attributionControl: true, zoomControl: true }).setView([home.lat, home.lng], 13)
    L.tileLayer(tileUrl(), { maxZoom: 19, subdomains: 'abcd', attribution: '© OpenStreetMap, © CARTO · ניתוב OSRM' }).addTo(map)
    layerRef.current = L.layerGroup().addTo(map)
    mapRef.current = map
    return () => { map.remove(); mapRef.current = null }
  }, [])

  useEffect(() => {
    const map = mapRef.current, layer = layerRef.current
    if (!map || !layer) return
    layer.clearLayers()

    const inPerson = stops.filter(s => !s.isRemote && s.loc)
    const points: [number, number][] = [
      [home.lat, home.lng],
      ...inPerson.map(s => [s.loc!.lat, s.loc!.lng] as [number, number]),
      [home.lat, home.lng],
    ]

    // instant straight-line preview (kept as fallback until roads arrive)
    const straight = L.polyline(points, { color: '#12917B', weight: 3, opacity: 0.45, dashArray: '2 8', lineCap: 'round' }).addTo(layer)

    // markers live in Leaflet's markerPane, always above the route line
    L.marker([home.lat, home.lng], { icon: marker('home', '🏠'), zIndexOffset: 500 }).bindPopup('בית המאמן').addTo(layer)
    inPerson.forEach((s, i) => {
      L.marker([s.loc!.lat, s.loc!.lng], { icon: marker('stop', String(i + 1)) })
        .bindPopup(`${i + 1}. ${s.label} · ${s.loc!.name}`).addTo(layer)
    })

    map.fitBounds(L.latLngBounds(points), { padding: [36, 36], maxZoom: 15 })
    setTimeout(() => map.invalidateSize(), 60)

    // upgrade to the real road route when it comes back
    let cancelled = false
    const ctrl = new AbortController()
    if (inPerson.length >= 1) {
      fetchRoad(points, ctrl.signal).then(road => {
        if (cancelled || !road) return
        layer.removeLayer(straight)
        L.polyline(road, { color: '#0C6E5D', weight: 5, opacity: 0.9, lineCap: 'round', lineJoin: 'round' }).addTo(layer)
      })
    }
    return () => { cancelled = true; ctrl.abort() }
  }, [home.lat, home.lng, JSON.stringify(stops.map(s => [s.loc?.lat, s.loc?.lng, s.isRemote]))])

  return <div className="routemap" ref={elRef} />
}
