// Live day-route map (Leaflet + free OSM/CARTO tiles, no API key).
// Draws home + the ordered in-person stops for one day, connected in route order.
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

export default function RouteMap({ home, stops }: Props) {
  const elRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerRef = useRef<L.LayerGroup | null>(null)

  // init once
  useEffect(() => {
    if (!elRef.current || mapRef.current) return
    const map = L.map(elRef.current, { attributionControl: true, zoomControl: true }).setView([home.lat, home.lng], 13)
    L.tileLayer(tileUrl(), { maxZoom: 19, subdomains: 'abcd', attribution: '© OpenStreetMap, © CARTO' }).addTo(map)
    layerRef.current = L.layerGroup().addTo(map)
    mapRef.current = map
    return () => { map.remove(); mapRef.current = null }
  }, [])

  // redraw on data change
  useEffect(() => {
    const map = mapRef.current, layer = layerRef.current
    if (!map || !layer) return
    layer.clearLayers()

    const inPerson = stops.filter(s => !s.isRemote && s.loc)
    const points: [number, number][] = [[home.lat, home.lng]]
    inPerson.forEach(s => points.push([s.loc!.lat, s.loc!.lng]))
    points.push([home.lat, home.lng]) // ride back home

    // route line
    L.polyline(points, { color: '#12917B', weight: 4, opacity: 0.85, dashArray: '2 8', lineCap: 'round' }).addTo(layer)

    // home + numbered stops
    L.marker([home.lat, home.lng], { icon: marker('home', '🏠'), zIndexOffset: 500 })
      .bindPopup('בית המאמן').addTo(layer)
    inPerson.forEach((s, i) => {
      L.marker([s.loc!.lat, s.loc!.lng], { icon: marker('stop', String(i + 1)) })
        .bindPopup(`${i + 1}. ${s.label} · ${s.loc!.name}`).addTo(layer)
    })

    const bounds = L.latLngBounds(points)
    map.fitBounds(bounds, { padding: [36, 36], maxZoom: 15 })
    setTimeout(() => map.invalidateSize(), 60) // ensure correct size after layout
  }, [home.lat, home.lng, JSON.stringify(stops.map(s => [s.loc?.lat, s.loc?.lng, s.isRemote]))])

  return <div className="routemap" ref={elRef} />
}
