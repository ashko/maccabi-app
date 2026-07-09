// Client-side scheduling engine: bike travel-time matrix (haversine estimate)
// plus a greedy VRPTW placer that mirrors the Python engine's fallback solver.
// Fixed sessions are anchors; flexible sessions are placed inside their windows
// so as to add the least riding, respecting buffers, work hours and daily caps.

import { DB, Loc, Plan, Scheduled, sundayOfISO, weekdayOfISO } from './domain'

const DETOUR = 1.35 // real routes are longer than crow-flies

function haversineKm(a: Loc, b: Loc): number {
  const R = 6371
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(s))
}

function rideMinutes(a: Loc, b: Loc, speedKmh: number): number {
  return Math.max(1, Math.round((haversineKm(a, b) * DETOUR) / speedKmh * 60))
}

interface Busy { start: number; end: number }

export function buildPlan(db: DB, weekStart: string): Plan {
  const { trainer, trainees, fixed, flexible } = db
  const traineeById = new Map(trainees.map(t => [t.id, t]))
  const speed = trainer.bikeSpeedKmh || 15
  const buffer = trainer.bufferMin

  const busy: Record<number, Busy[]> = {}
  const count: Record<number, number> = {}
  for (const d of Object.keys(trainer.workHours).map(Number)) {
    busy[d] = []
    count[d] = 0
  }

  const sessions: Scheduled[] = []
  const unscheduled: string[] = []

  const fits = (day: number, start: number, dur: number): boolean => {
    const wh = trainer.workHours[day]
    if (!wh) return false
    const [ws, we] = wh
    if (start < ws || start + dur > we || (count[day] ?? 0) >= trainer.maxPerDay) return false
    const s0 = start, s1 = start + dur
    return busy[day].every(b => s1 + buffer <= b.start || s0 - buffer >= b.end)
  }
  const reserve = (day: number, start: number, dur: number) => {
    busy[day].push({ start: start - buffer, end: start + dur + buffer })
    count[day] = (count[day] ?? 0) + 1
  }

  // 1) fixed anchors — weekly ones always apply; one-time only in their own week
  for (const f of fixed) {
    const tr = traineeById.get(f.traineeId)
    if (!tr) continue
    let weekday = f.weekday
    if ((f.recurrence || 'weekly') === 'once') {
      if (!f.date || sundayOfISO(f.date) !== weekStart) continue
      weekday = weekdayOfISO(f.date)
    }
    if (fits(weekday, f.start, f.duration)) {
      reserve(weekday, f.start, f.duration)
      sessions.push({
        traineeId: f.traineeId, label: f.label, category: f.category,
        weekday, start: f.start, end: f.start + f.duration,
        isRemote: f.isRemote, loc: f.isRemote ? null : tr.location, order: 0, travelFromPrev: 0,
      })
    } else {
      unscheduled.push(`אימון קבוע לא שובץ (קונפליקט): ${tr.name} — ${f.label}`)
    }
  }

  // 2) flexible — one-time only in their target week; tightest (fewest windows) first
  const ordered = [...flexible]
    .filter(r => (r.recurrence || 'weekly') !== 'once' || r.targetWeek === weekStart)
    .sort((a, b) => a.availability.length - b.availability.length)
  for (const r of ordered) {
    const tr = traineeById.get(r.traineeId)
    if (!tr) continue
    let best: { day: number; start: number; cost: number } | null = null

    for (const w of r.availability) {
      for (let start = w.start; start + r.duration <= w.end; start += 5) {
        if (!fits(w.weekday, start, r.duration)) continue
        let cost = 0
        if (!r.isRemote) {
          const here = tr.location
          const sameDay = sessions.filter(s => s.weekday === w.weekday && s.loc)
          cost = sameDay.length
            ? Math.min(...sameDay.map(s => rideMinutes(s.loc as Loc, here, speed)))
            : rideMinutes(trainer.home, here, speed)
        }
        if (!best || cost < best.cost) best = { day: w.weekday, start, cost }
        break // earliest feasible start per window is enough
      }
    }

    if (best) {
      reserve(best.day, best.start, r.duration)
      sessions.push({
        traineeId: r.traineeId, label: r.label, category: r.category,
        weekday: best.day, start: best.start, end: best.start + r.duration,
        isRemote: r.isRemote, loc: r.isRemote ? null : tr.location, order: 0, travelFromPrev: 0,
      })
    } else {
      unscheduled.push(`אימון משתנה לא שובץ (אין חלון פנוי): ${tr.name} — ${r.label}`)
    }
  }

  // 3) per-day route metrics
  let totalRide = 0
  const byDay: Record<number, Scheduled[]> = {}
  for (const s of sessions) (byDay[s.weekday] ||= []).push(s)
  for (const day of Object.keys(byDay).map(Number)) {
    const list = byDay[day].sort((a, b) => a.start - b.start)
    let prev: Loc = trainer.home
    list.forEach((s, i) => {
      s.order = i + 1
      if (s.isRemote || !s.loc) { s.travelFromPrev = 0; return }
      const leg = rideMinutes(prev, s.loc, speed)
      s.travelFromPrev = leg
      totalRide += leg
      prev = s.loc
    })
    if (prev !== trainer.home) totalRide += rideMinutes(prev, trainer.home, speed)
  }

  return { weekStart, sessions, unscheduled, totalRide }
}
