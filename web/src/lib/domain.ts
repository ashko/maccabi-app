// Domain types, time helpers and the seed roster.
// Time is minutes-from-midnight; weekday 0 = Sunday .. 5 = Friday (Israeli week).

export type Category = 'physical' | 'nutrition'

export interface Loc { name: string; lat: number; lng: number }

export interface Trainee {
  id: string
  name: string
  phone: string          // international, e.g. +972501234567
  location: Loc
  consent: boolean       // opt-in to receive WhatsApp messages
}

export interface Trainer {
  home: Loc
  workHours: Record<number, [number, number]>  // weekday -> [start, end]
  bufferMin: number
  maxPerDay: number
  bikeSpeedKmh: number
}

export interface Fixed {
  id: string
  traineeId: string
  label: string
  category: Category
  duration: number
  weekday: number
  start: number
  isRemote: boolean
}

export interface Window { weekday: number; start: number; end: number }

export interface Flexible {
  id: string
  traineeId: string
  label: string
  category: Category
  duration: number
  isRemote: boolean
  availability: Window[]
}

export interface Scheduled {
  traineeId: string
  label: string
  category: Category
  weekday: number
  start: number
  end: number
  isRemote: boolean
  loc: Loc | null
  order: number
  travelFromPrev: number
}

export interface Plan {
  weekStart: string
  sessions: Scheduled[]
  unscheduled: string[]
  totalRide: number
}

export interface DB {
  trainer: Trainer
  trainees: Trainee[]
  fixed: Fixed[]
  flexible: Flexible[]
}

export const WEEKDAYS_HE = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת']
export const WORK_DAYS = [0, 1, 2, 3, 4, 5]
export const CATEGORY_HE: Record<Category, string> = {
  physical: 'אימון גופני',
  nutrition: 'אימון תזונה',
}

export const hm = (h: number, m: number) => h * 60 + m
export const fmtHm = (min: number) =>
  `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`
export const parseHm = (s: string) => {
  const [h, m] = s.split(':').map(Number)
  return h * 60 + m
}
export const uid = () =>
  (crypto?.randomUUID ? crypto.randomUUID() : 'id-' + Math.floor(performance.now() * 1000).toString(36))

// ---- seed roster (Tel Aviv) shown on first run ---------------------------- //

export function seedDB(): DB {
  const t = (id: string, name: string, phone: string, area: string, lat: number, lng: number, consent = true): Trainee =>
    ({ id, name, phone, location: { name: area, lat, lng }, consent })

  const trainees: Trainee[] = [
    t('t1', 'דנה', '+972500000001', 'הצפון הישן, תל אביב', 32.09, 34.781),
    t('t2', 'יוסי', '+972500000002', 'פלורנטין, תל אביב', 32.056, 34.769),
    t('t3', 'רון', '+972500000003', 'רמת אביב, תל אביב', 32.113, 34.796),
    t('t4', 'מיה', '+972500000004', 'נווה צדק, תל אביב', 32.062, 34.764),
    t('t5', 'עדי', '+972500000005', 'יד אליהו, תל אביב', 32.053, 34.796, false),
    t('t6', 'טל', '+972500000006', 'בבלי, תל אביב', 32.098, 34.79),
  ]

  const workHours: Record<number, [number, number]> = {
    0: [hm(8, 0), hm(18, 0)],
    1: [hm(8, 0), hm(18, 0)],
    2: [hm(8, 0), hm(18, 0)],
    3: [hm(7, 0), hm(18, 0)],
    4: [hm(8, 0), hm(18, 0)],
  }

  const trainer: Trainer = {
    home: { name: 'לב תל אביב', lat: 32.0705, lng: 34.7805 },
    workHours, bufferMin: 15, maxPerDay: 6, bikeSpeedKmh: 15,
  }

  const fixed: Fixed[] = [
    { id: uid(), traineeId: 't3', label: 'כוח קבוע', category: 'physical', duration: 60, weekday: 1, start: hm(9, 0), isRemote: false },
    { id: uid(), traineeId: 't1', label: 'ריצה קבועה', category: 'physical', duration: 45, weekday: 3, start: hm(7, 30), isRemote: false },
    { id: uid(), traineeId: 't6', label: 'תזונה קבועה', category: 'nutrition', duration: 30, weekday: 2, start: hm(16, 0), isRemote: false },
  ]

  const win = (weekday: number, s: string, e: string): Window => ({ weekday, start: parseHm(s), end: parseHm(e) })
  const flexible: Flexible[] = [
    { id: uid(), traineeId: 't1', label: 'HIIT', category: 'physical', duration: 45, isRemote: false, availability: [win(0, '08:00', '12:00'), win(2, '09:00', '13:00')] },
    { id: uid(), traineeId: 't2', label: 'כוח', category: 'physical', duration: 60, isRemote: false, availability: [win(0, '08:00', '11:00'), win(4, '14:00', '18:00')] },
    { id: uid(), traineeId: 't4', label: 'פונקציונלי', category: 'physical', duration: 45, isRemote: false, availability: WORK_DAYS.slice(0, 5).map(d => ({ weekday: d, start: hm(8, 0), end: hm(13, 0) })) },
    { id: uid(), traineeId: 't5', label: 'ייעוץ תזונה', category: 'nutrition', duration: 30, isRemote: true, availability: [win(1, '10:00', '14:00')] },
    { id: uid(), traineeId: 't2', label: 'תזונה', category: 'nutrition', duration: 30, isRemote: true, availability: [win(3, '15:00', '18:00')] },
    { id: uid(), traineeId: 't6', label: 'כוח', category: 'physical', duration: 60, isRemote: false, availability: [win(0, '08:00', '13:00'), win(4, '08:00', '13:00')] },
  ]

  return { trainer, trainees, fixed, flexible }
}
