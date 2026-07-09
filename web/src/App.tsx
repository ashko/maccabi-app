import { useEffect, useMemo, useState } from 'react'
import AddressSearch from './components/AddressSearch'
import {
  CATEGORY_HE, Category, DB, Fixed, Flexible, Loc, Plan, Scheduled, Trainee,
  WEEKDAYS_HE, WORK_DAYS, fmtHm, parseHm, uid,
} from './lib/domain'
import { loadDB, resetDB, saveDB } from './lib/store'
import { buildPlan } from './lib/scheduler'
import { renderMessage, waLink } from './lib/whatsapp'

type View = 'people' | 'trainings' | 'plan' | 'send' | 'settings'

const NAV: { id: View; label: string; icon: string }[] = [
  { id: 'people', label: 'מתאמנים', icon: '👥' },
  { id: 'trainings', label: 'אימונים', icon: '🏋️' },
  { id: 'plan', label: 'לו״ז', icon: '📅' },
  { id: 'send', label: 'שליחה', icon: '💬' },
  { id: 'settings', label: 'הגדרות', icon: '⚙️' },
]

export default function App() {
  const [db, setDb] = useState<DB>(() => loadDB())
  const [view, setView] = useState<View>('people')
  const [plan, setPlan] = useState<Plan | null>(null)
  const [installEvt, setInstallEvt] = useState<any>(null)

  const commit = (next: DB) => { saveDB(next); setDb({ ...next }) }

  useEffect(() => {
    const h = (e: any) => { e.preventDefault(); setInstallEvt(e) }
    window.addEventListener('beforeinstallprompt', h)
    return () => window.removeEventListener('beforeinstallprompt', h)
  }, [])

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand"><span className="logo">🚴</span> RideCoach</div>
        {installEvt && (
          <button className="ghost sm" onClick={async () => { installEvt.prompt(); setInstallEvt(null) }}>
            התקן לאפליקציה
          </button>
        )}
      </header>

      <main className="content">
        {view === 'people' && <People db={db} commit={commit} />}
        {view === 'trainings' && <Trainings db={db} commit={commit} />}
        {view === 'plan' && <PlanView db={db} plan={plan} setPlan={setPlan} />}
        {view === 'send' && <SendView db={db} plan={plan} />}
        {view === 'settings' && <Settings db={db} commit={commit} setDb={setDb} />}
      </main>

      <nav className="tabbar">
        {NAV.map(n => (
          <button key={n.id} className={'tab' + (view === n.id ? ' active' : '')} onClick={() => setView(n.id)}>
            <span className="ic">{n.icon}</span>
            <span className="tl">{n.label}</span>
          </button>
        ))}
      </nav>
    </div>
  )
}

// --------------------------------------------------------------------------- //
//  shared bits
// --------------------------------------------------------------------------- //

function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: any }) {
  return (
    <div className="scrim" onClick={onClose}>
      <div className="sheet" onClick={e => e.stopPropagation()}>
        <div className="sheet-head">
          <h3>{title}</h3>
          <button className="ghost sm" onClick={onClose}>✕</button>
        </div>
        <div className="sheet-body">{children}</div>
      </div>
    </div>
  )
}

const catName = (c: Category) => CATEGORY_HE[c]
function useTrainees(db: DB) {
  return useMemo(() => new Map(db.trainees.map(t => [t.id, t])), [db.trainees])
}

// --------------------------------------------------------------------------- //
//  People
// --------------------------------------------------------------------------- //

function People({ db, commit }: { db: DB; commit: (d: DB) => void }) {
  const [edit, setEdit] = useState<Trainee | null>(null)
  const [adding, setAdding] = useState(false)

  const blank = (): Trainee => ({ id: uid(), name: '', phone: '+972', location: { name: '', lat: 0, lng: 0 }, consent: false })

  const save = (t: Trainee) => {
    const exists = db.trainees.some(x => x.id === t.id)
    const trainees = exists ? db.trainees.map(x => (x.id === t.id ? t : x)) : [...db.trainees, t]
    commit({ ...db, trainees })
    setEdit(null); setAdding(false)
  }
  const remove = (id: string) => {
    commit({
      ...db,
      trainees: db.trainees.filter(t => t.id !== id),
      fixed: db.fixed.filter(f => f.traineeId !== id),
      flexible: db.flexible.filter(f => f.traineeId !== id),
    })
    setEdit(null)
  }

  return (
    <section>
      <div className="view-head">
        <h2>מתאמנים</h2>
        <button className="primary" onClick={() => setAdding(true)}>➕ הוסף</button>
      </div>
      <div className="list">
        {db.trainees.map(t => (
          <button className="row card" key={t.id} onClick={() => setEdit(t)}>
            <div className="avatar">{t.name.slice(0, 1) || '?'}</div>
            <div className="grow">
              <div className="row-title">{t.name || 'ללא שם'}</div>
              <div className="row-sub">{t.location.name || 'ללא כתובת'} · {t.phone}</div>
            </div>
            <span className={'pill ' + (t.consent ? 'ok' : 'off')}>{t.consent ? 'הסכמה ✓' : 'ללא הסכמה'}</span>
          </button>
        ))}
        {db.trainees.length === 0 && <Empty text="אין מתאמנים עדיין" />}
      </div>

      {(edit || adding) && (
        <TraineeForm
          initial={edit || blank()}
          onClose={() => { setEdit(null); setAdding(false) }}
          onSave={save}
          onDelete={edit ? () => remove(edit.id) : undefined}
        />
      )}
    </section>
  )
}

function TraineeForm({ initial, onClose, onSave, onDelete }:
  { initial: Trainee; onClose: () => void; onSave: (t: Trainee) => void; onDelete?: () => void }) {
  const [t, setT] = useState<Trainee>(initial)
  const valid = t.name.trim() && t.location.lat !== 0
  return (
    <Sheet title={onDelete ? 'עריכת מתאמן' : 'מתאמן חדש'} onClose={onClose}>
      <label className="lbl">שם</label>
      <input className="input" value={t.name} onChange={e => setT({ ...t, name: e.target.value })} />

      <label className="lbl">כתובת</label>
      <AddressSearch value={t.location.lat ? t.location : null} onChange={loc => setT({ ...t, location: loc })} />

      <label className="lbl">טלפון (וואטסאפ, כולל קידומת מדינה)</label>
      <input className="input" inputMode="tel" value={t.phone} onChange={e => setT({ ...t, phone: e.target.value })} />

      <label className="switch">
        <input type="checkbox" checked={t.consent} onChange={e => setT({ ...t, consent: e.target.checked })} />
        <span>הסכמה לקבלת הודעות וואטסאפ</span>
      </label>

      <div className="actions">
        {onDelete && <button className="danger" onClick={onDelete}>🗑️ מחק</button>}
        <button className="primary grow" disabled={!valid} onClick={() => onSave(t)}>💾 שמור</button>
      </div>
      {!valid && <p className="hint">יש להזין שם ולבחור כתובת מהרשימה.</p>}
    </Sheet>
  )
}

// --------------------------------------------------------------------------- //
//  Trainings (fixed + flexible)
// --------------------------------------------------------------------------- //

function Trainings({ db, commit }: { db: DB; commit: (d: DB) => void }) {
  const [seg, setSeg] = useState<'fixed' | 'flex'>('fixed')
  const trainees = useTrainees(db)
  return (
    <section>
      <div className="view-head"><h2>אימונים</h2></div>
      <div className="seg">
        <button className={seg === 'fixed' ? 'on' : ''} onClick={() => setSeg('fixed')}>קבועים</button>
        <button className={seg === 'flex' ? 'on' : ''} onClick={() => setSeg('flex')}>שבועיים</button>
      </div>
      {seg === 'fixed'
        ? <FixedList db={db} commit={commit} trainees={trainees} />
        : <FlexList db={db} commit={commit} trainees={trainees} />}
    </section>
  )
}

function FixedList({ db, commit, trainees }: { db: DB; commit: (d: DB) => void; trainees: Map<string, Trainee> }) {
  const [adding, setAdding] = useState(false)
  if (db.trainees.length === 0) return <Empty text="הוסף מתאמנים תחילה" />
  return (
    <>
      <div className="list">
        {db.fixed.map(f => (
          <div className="row card" key={f.id}>
            <div className="grow">
              <div className="row-title">{trainees.get(f.traineeId)?.name} · {f.label}</div>
              <div className="row-sub">{catName(f.category)} · {WEEKDAYS_HE[f.weekday]} {fmtHm(f.start)} · {f.duration} דק׳{f.isRemote ? ' · אונליין' : ''}</div>
            </div>
            <button className="ghost sm" onClick={() => commit({ ...db, fixed: db.fixed.filter(x => x.id !== f.id) })}>🗑️</button>
          </div>
        ))}
        {db.fixed.length === 0 && <Empty text="אין אימונים קבועים" />}
      </div>
      <button className="primary block" onClick={() => setAdding(true)}>➕ אימון קבוע</button>
      {adding && (
        <FixedForm db={db} onClose={() => setAdding(false)} onSave={f => { commit({ ...db, fixed: [...db.fixed, f] }); setAdding(false) }} />
      )}
    </>
  )
}

function FixedForm({ db, onClose, onSave }: { db: DB; onClose: () => void; onSave: (f: Fixed) => void }) {
  const [f, setF] = useState<Fixed>({
    id: uid(), traineeId: db.trainees[0].id, label: 'כוח', category: 'physical',
    duration: 60, weekday: 0, start: parseHm('09:00'), isRemote: false,
  })
  return (
    <Sheet title="אימון קבוע" onClose={onClose}>
      <TraineePick db={db} value={f.traineeId} onChange={id => setF({ ...f, traineeId: id })} />
      <label className="lbl">שם האימון</label>
      <input className="input" value={f.label} onChange={e => setF({ ...f, label: e.target.value })} />
      <CategoryPick value={f.category} onChange={c => setF({ ...f, category: c })} />
      <div className="grid2">
        <div>
          <label className="lbl">יום</label>
          <select className="input" value={f.weekday} onChange={e => setF({ ...f, weekday: Number(e.target.value) })}>
            {WORK_DAYS.map(d => <option key={d} value={d}>{WEEKDAYS_HE[d]}</option>)}
          </select>
        </div>
        <div>
          <label className="lbl">שעה</label>
          <input type="time" className="input" value={fmtHm(f.start)} step={900} onChange={e => setF({ ...f, start: parseHm(e.target.value) })} />
        </div>
      </div>
      <DurationRemote duration={f.duration} isRemote={f.isRemote}
        onDur={d => setF({ ...f, duration: d })} onRemote={r => setF({ ...f, isRemote: r })} />
      <div className="actions"><button className="primary grow" onClick={() => onSave(f)}>💾 הוסף</button></div>
    </Sheet>
  )
}

function FlexList({ db, commit, trainees }: { db: DB; commit: (d: DB) => void; trainees: Map<string, Trainee> }) {
  const [adding, setAdding] = useState(false)
  if (db.trainees.length === 0) return <Empty text="הוסף מתאמנים תחילה" />
  return (
    <>
      <div className="list">
        {db.flexible.map(r => (
          <div className="row card" key={r.id}>
            <div className="grow">
              <div className="row-title">{trainees.get(r.traineeId)?.name} · {r.label}</div>
              <div className="row-sub">{catName(r.category)} · {r.duration} דק׳{r.isRemote ? ' · אונליין' : ''}</div>
              <div className="row-sub dim">{r.availability.map(w => `${WEEKDAYS_HE[w.weekday]} ${fmtHm(w.start)}-${fmtHm(w.end)}`).join(' · ')}</div>
            </div>
            <button className="ghost sm" onClick={() => commit({ ...db, flexible: db.flexible.filter(x => x.id !== r.id) })}>🗑️</button>
          </div>
        ))}
        {db.flexible.length === 0 && <Empty text="אין בקשות שבועיות" />}
      </div>
      <button className="primary block" onClick={() => setAdding(true)}>➕ בקשה שבועית</button>
      {adding && (
        <FlexForm db={db} onClose={() => setAdding(false)} onSave={r => { commit({ ...db, flexible: [...db.flexible, r] }); setAdding(false) }} />
      )}
    </>
  )
}

function FlexForm({ db, onClose, onSave }: { db: DB; onClose: () => void; onSave: (r: Flexible) => void }) {
  const [r, setR] = useState<Flexible>({
    id: uid(), traineeId: db.trainees[0].id, label: 'HIIT', category: 'physical',
    duration: 45, isRemote: false, availability: [],
  })
  const [days, setDays] = useState<Record<number, { on: boolean; from: string; to: string }>>(
    Object.fromEntries(WORK_DAYS.map(d => [d, { on: false, from: '08:00', to: '13:00' }])))

  const build = () => {
    const availability = WORK_DAYS.filter(d => days[d].on)
      .map(d => ({ weekday: d, start: parseHm(days[d].from), end: parseHm(days[d].to) }))
    if (availability.length) onSave({ ...r, availability })
  }
  const anyDay = WORK_DAYS.some(d => days[d].on)

  return (
    <Sheet title="בקשה שבועית" onClose={onClose}>
      <TraineePick db={db} value={r.traineeId} onChange={id => setR({ ...r, traineeId: id })} />
      <label className="lbl">שם האימון</label>
      <input className="input" value={r.label} onChange={e => setR({ ...r, label: e.target.value })} />
      <CategoryPick value={r.category} onChange={c => setR({ ...r, category: c })} />
      <DurationRemote duration={r.duration} isRemote={r.isRemote}
        onDur={d => setR({ ...r, duration: d })} onRemote={x => setR({ ...r, isRemote: x })} />
      <label className="lbl">חלונות זמינות</label>
      <div className="avail">
        {WORK_DAYS.map(d => (
          <div className={'avail-row' + (days[d].on ? ' on' : '')} key={d}>
            <label className="switch tight">
              <input type="checkbox" checked={days[d].on} onChange={e => setDays({ ...days, [d]: { ...days[d], on: e.target.checked } })} />
              <span>{WEEKDAYS_HE[d]}</span>
            </label>
            {days[d].on && (
              <div className="times">
                <input type="time" className="input sm" value={days[d].from} step={900} onChange={e => setDays({ ...days, [d]: { ...days[d], from: e.target.value } })} />
                <span>–</span>
                <input type="time" className="input sm" value={days[d].to} step={900} onChange={e => setDays({ ...days, [d]: { ...days[d], to: e.target.value } })} />
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="actions"><button className="primary grow" disabled={!anyDay} onClick={build}>💾 הוסף</button></div>
    </Sheet>
  )
}

function TraineePick({ db, value, onChange }: { db: DB; value: string; onChange: (id: string) => void }) {
  return (
    <>
      <label className="lbl">מתאמן</label>
      <select className="input" value={value} onChange={e => onChange(e.target.value)}>
        {db.trainees.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
      </select>
    </>
  )
}
function CategoryPick({ value, onChange }: { value: Category; onChange: (c: Category) => void }) {
  return (
    <>
      <label className="lbl">סוג</label>
      <div className="seg small">
        <button className={value === 'physical' ? 'on' : ''} onClick={() => onChange('physical')}>גופני</button>
        <button className={value === 'nutrition' ? 'on' : ''} onClick={() => onChange('nutrition')}>תזונה</button>
      </div>
    </>
  )
}
function DurationRemote({ duration, isRemote, onDur, onRemote }:
  { duration: number; isRemote: boolean; onDur: (d: number) => void; onRemote: (r: boolean) => void }) {
  return (
    <div className="grid2">
      <div>
        <label className="lbl">משך (דק׳)</label>
        <select className="input" value={duration} onChange={e => onDur(Number(e.target.value))}>
          {[30, 45, 60, 75, 90].map(d => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>
      <label className="switch end">
        <input type="checkbox" checked={isRemote} onChange={e => onRemote(e.target.checked)} />
        <span>אונליין 💻</span>
      </label>
    </div>
  )
}

// --------------------------------------------------------------------------- //
//  Plan
// --------------------------------------------------------------------------- //

function nextSundayISO(): string {
  const now = new Date()
  const day = now.getDay() // 0=Sun
  const add = day === 0 ? 7 : 7 - day
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + add)
  return d.toISOString().slice(0, 10)
}

function PlanView({ db, plan, setPlan }: { db: DB; plan: Plan | null; setPlan: (p: Plan) => void }) {
  const [week, setWeek] = useState<string>(nextSundayISO())
  const trainees = useTrainees(db)
  const byDay = useMemo(() => {
    const m: Record<number, Scheduled[]> = {}
    plan?.sessions.forEach(s => (m[s.weekday] ||= []).push(s))
    Object.values(m).forEach(l => l.sort((a, b) => a.start - b.start))
    return m
  }, [plan])

  return (
    <section>
      <div className="view-head"><h2>לו״ז שבועי</h2></div>
      <div className="card pad">
        <label className="lbl">שבוע שמתחיל ביום ראשון</label>
        <input type="date" className="input" value={week} onChange={e => setWeek(e.target.value)} />
        <button className="primary block" onClick={() => setPlan(buildPlan(db, week))}>🧮 בנה לו״ז</button>
      </div>

      {plan && (
        <>
          <div className="metrics">
            <Metric v={`${plan.totalRide}`} u="דק׳ רכיבה" />
            <Metric v={`${plan.sessions.length}`} u="אימונים" />
            <Metric v={`${plan.unscheduled.length}`} u="קונפליקטים" warn={plan.unscheduled.length > 0} />
          </div>

          {plan.unscheduled.length > 0 && (
            <div className="alert">
              {plan.unscheduled.map((u, i) => <div key={i}>⚠️ {u}</div>)}
            </div>
          )}

          {WORK_DAYS.filter(d => byDay[d]?.length).map(d => (
            <div className="day card" key={d}>
              <div className="day-head">יום {WEEKDAYS_HE[d]}</div>
              {byDay[d].map((s, i) => (
                <div className="slot" key={i}>
                  <div className="slot-time">{fmtHm(s.start)}<span>{fmtHm(s.end)}</span></div>
                  <div className="grow">
                    <div className="row-title">{trainees.get(s.traineeId)?.name} · {s.label}</div>
                    <div className="row-sub">{catName(s.category)} · {s.isRemote ? 'אונליין 💻' : s.loc?.name}</div>
                  </div>
                  <div className="ride">{s.isRemote ? '💻' : `🚲 ${s.travelFromPrev}′`}</div>
                </div>
              ))}
            </div>
          ))}
        </>
      )}
      {!plan && <Empty text="בחר שבוע ולחץ ״בנה לו״ז״" />}
    </section>
  )
}

function Metric({ v, u, warn }: { v: string; u: string; warn?: boolean }) {
  return <div className={'metric' + (warn ? ' warn' : '')}><div className="mv">{v}</div><div className="mu">{u}</div></div>
}

// --------------------------------------------------------------------------- //
//  Send
// --------------------------------------------------------------------------- //

function SendView({ db, plan }: { db: DB; plan: Plan | null }) {
  const trainees = useTrainees(db)
  const [sent, setSent] = useState<Record<string, boolean>>({})
  if (!plan) return <section><div className="view-head"><h2>שליחה</h2></div><Empty text="בנה לו״ז תחילה" /></section>

  const items = [...plan.sessions].sort((a, b) => a.weekday - b.weekday || a.start - b.start)
  return (
    <section>
      <div className="view-head"><h2>שליחת וואטסאפ</h2></div>
      <p className="hint">לחיצה פותחת את וואטסאפ עם ההודעה מוכנה — רק ללחוץ שלח. בלי עלות ובלי הגדרות.</p>
      <div className="list">
        {items.map((s, i) => {
          const tr = trainees.get(s.traineeId)!
          const key = `${s.traineeId}-${s.weekday}-${s.start}`
          const msg = renderMessage(s, tr)
          return (
            <div className="card send-card" key={i}>
              <div className="send-top">
                <div className="grow">
                  <div className="row-title">{tr.name}</div>
                  <div className="row-sub">{WEEKDAYS_HE[s.weekday]} {fmtHm(s.start)} · {s.label}</div>
                </div>
                {!tr.consent && <span className="pill off">אין הסכמה</span>}
                {sent[key] && <span className="pill ok">נשלח ✓</span>}
              </div>
              <div className="bubble">{msg}</div>
              <a
                className={'wa' + (tr.consent ? '' : ' disabled')}
                href={tr.consent ? waLink(tr, msg) : undefined}
                target="_blank" rel="noreferrer"
                onClick={() => tr.consent && setSent(p => ({ ...p, [key]: true }))}
              >
                <span>שלח בוואטסאפ</span> <span>➤</span>
              </a>
            </div>
          )
        })}
      </div>
    </section>
  )
}

// --------------------------------------------------------------------------- //
//  Settings
// --------------------------------------------------------------------------- //

function Settings({ db, commit, setDb }: { db: DB; commit: (d: DB) => void; setDb: (d: DB) => void }) {
  const tr = db.trainer
  const setHours = (d: number, on: boolean, from?: string, to?: string) => {
    const wh = { ...tr.workHours }
    if (on) wh[d] = [from ? parseHm(from) : (wh[d]?.[0] ?? parseHm('08:00')), to ? parseHm(to) : (wh[d]?.[1] ?? parseHm('18:00'))]
    else delete wh[d]
    commit({ ...db, trainer: { ...tr, workHours: wh } })
  }
  return (
    <section>
      <div className="view-head"><h2>הגדרות</h2></div>

      <div className="card pad">
        <label className="lbl">כתובת הבית (נקודת מוצא לרכיבה)</label>
        <AddressSearch value={tr.home.lat ? tr.home : null} onChange={loc => commit({ ...db, trainer: { ...tr, home: loc } })} />
      </div>

      <div className="card pad">
        <label className="lbl">שעות עבודה</label>
        <div className="avail">
          {WORK_DAYS.map(d => {
            const wh = tr.workHours[d]
            return (
              <div className={'avail-row' + (wh ? ' on' : '')} key={d}>
                <label className="switch tight">
                  <input type="checkbox" checked={!!wh} onChange={e => setHours(d, e.target.checked)} />
                  <span>{WEEKDAYS_HE[d]}</span>
                </label>
                {wh && (
                  <div className="times">
                    <input type="time" className="input sm" step={900} value={fmtHm(wh[0])} onChange={e => setHours(d, true, e.target.value, fmtHm(wh[1]))} />
                    <span>–</span>
                    <input type="time" className="input sm" step={900} value={fmtHm(wh[1])} onChange={e => setHours(d, true, fmtHm(wh[0]), e.target.value)} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      <div className="card pad grid2">
        <div>
          <label className="lbl">מרווח בין אימונים (דק׳)</label>
          <select className="input" value={tr.bufferMin} onChange={e => commit({ ...db, trainer: { ...tr, bufferMin: Number(e.target.value) } })}>
            {[0, 5, 10, 15, 20, 30].map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div>
          <label className="lbl">מקס׳ אימונים ליום</label>
          <select className="input" value={tr.maxPerDay} onChange={e => commit({ ...db, trainer: { ...tr, maxPerDay: Number(e.target.value) } })}>
            {[3, 4, 5, 6, 7, 8, 10].map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div>
          <label className="lbl">מהירות רכיבה (קמ״ש)</label>
          <select className="input" value={tr.bikeSpeedKmh} onChange={e => commit({ ...db, trainer: { ...tr, bikeSpeedKmh: Number(e.target.value) } })}>
            {[12, 14, 15, 16, 18, 20].map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
      </div>

      <button className="danger block" onClick={() => { if (confirm('לאפס לנתוני הדוגמה? כל השינויים יימחקו.')) setDb(resetDB()) }}>
        איפוס לנתוני דוגמה
      </button>
      <p className="hint center">הנתונים נשמרים במכשיר שלך בלבד. פרטי וחינמי.</p>
    </section>
  )
}

function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>
}
