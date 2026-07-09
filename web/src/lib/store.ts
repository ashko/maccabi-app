// On-device persistence via localStorage — private, free, no backend.
import { DB, migrateDB, seedDB } from './domain'

const KEY = 'ridecoach.db.v1'

export function loadDB(): DB {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) return migrateDB(JSON.parse(raw) as DB)
  } catch {
    /* corrupt or unavailable — fall through to seed */
  }
  const db = seedDB()
  saveDB(db)
  return db
}

export function saveDB(db: DB): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(db))
  } catch {
    /* storage full / disabled — data stays in memory for the session */
  }
}

export function resetDB(): DB {
  const db = seedDB()
  saveDB(db)
  return db
}
