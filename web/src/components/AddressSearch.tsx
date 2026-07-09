// Modern type-ahead address field. Debounced Photon lookups, keyboard-free
// tap-to-select on mobile. Emits a Loc (label + hidden coordinates).
import { useEffect, useRef, useState } from 'react'
import { Loc } from '../lib/domain'
import { searchAddress } from '../lib/geocode'

interface Props {
  value: Loc | null
  onChange: (loc: Loc) => void
  placeholder?: string
}

export default function AddressSearch({ value, onChange, placeholder }: Props) {
  const [text, setText] = useState(value?.name ?? '')
  const [results, setResults] = useState<Loc[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => { setText(value?.name ?? '') }, [value?.name])

  useEffect(() => {
    if (!open) return
    const q = text.trim()
    if (q.length < 2) { setResults([]); return }
    setLoading(true); setErr(false)
    const ctrl = new AbortController()
    abortRef.current?.abort()
    abortRef.current = ctrl
    const timer = setTimeout(async () => {
      try {
        const r = await searchAddress(q, ctrl.signal)
        setResults(r)
      } catch (e: any) {
        if (e?.name !== 'AbortError') setErr(true)
      } finally {
        setLoading(false)
      }
    }, 280)
    return () => { clearTimeout(timer); ctrl.abort() }
  }, [text, open])

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const pick = (loc: Loc) => {
    onChange(loc)
    setText(loc.name)
    setOpen(false)
    setResults([])
  }

  return (
    <div className="addr" ref={boxRef}>
      <input
        className="input"
        value={text}
        placeholder={placeholder || 'התחל להקליד כתובת…'}
        onFocus={() => setOpen(true)}
        onChange={e => { setText(e.target.value); setOpen(true) }}
        autoComplete="off"
      />
      {open && (text.trim().length >= 2) && (
        <div className="addr-menu">
          {loading && <div className="addr-item muted">מחפש…</div>}
          {err && <div className="addr-item muted">אין חיבור לרשת — נסה שוב</div>}
          {!loading && !err && results.length === 0 && (
            <div className="addr-item muted">לא נמצאו תוצאות</div>
          )}
          {results.map((r, i) => (
            <button type="button" key={i} className="addr-item" onClick={() => pick(r)}>
              <span className="pin">📍</span>{r.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
