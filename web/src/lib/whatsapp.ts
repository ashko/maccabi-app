// WhatsApp via wa.me deep links — free, no Business API, opens the native app
// with the personalised message pre-filled for the trainer to send in one tap.
import { CATEGORY_HE, Scheduled, Trainee, WEEKDAYS_HE, fmtHm } from './domain'

export function renderMessage(s: Scheduled, trainee: Trainee): string {
  const where = s.isRemote ? 'אונליין 💻' : s.loc?.name || 'ייסגר בהמשך'
  const kind = CATEGORY_HE[s.category]
  return (
    `היי ${trainee.name}, הנה האימון שלך לשבוע הבא: ` +
    `${kind} (${s.label}) ביום ${WEEKDAYS_HE[s.weekday]} ` +
    `בשעה ${fmtHm(s.start)} — ${where}. נתראה! 🚴`
  )
}

export function waLink(trainee: Trainee, message: string): string {
  const digits = trainee.phone.replace(/[^0-9]/g, '')
  return `https://wa.me/${digits}?text=${encodeURIComponent(message)}`
}
