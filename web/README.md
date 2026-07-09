# RideCoach PWA 🚴📱

אפליקציית web מודרנית (מובייל + דסקטופ) למאמן — שיבוץ אימונים שבועי, אופטימיזציית
מסלול אופניים ושליחת וואטסאפ. **מותקנת למסך הבית**, עובדת גם אופליין, ובעלות אפס.

## הרצה מקומית

```bash
cd web
npm install
npm run dev        # פיתוח
npm run build      # בנייה לפרודקשן (dist/)
npm run preview    # תצוגה מקדימה של הבנייה
```

## למה זה חינמי לגמרי

| יכולת | פתרון חינמי |
|------|-------------|
| חיפוש כתובת עם השלמה | Photon (Komoot) — ללא מפתח, ללא קואורדינטות ידניות |
| אופטימיזציית מסלול | מחושבת במכשיר (הערכת זמן רכיבה) — ללא שרת |
| שליחת וואטסאפ | קישורי `wa.me` שפותחים את האפליקציה עם ההודעה מוכנה — ללא Business API |
| אחסון נתונים | `localStorage` במכשיר + סנכרון ענן אופציונלי (Vercel KV) |
| אירוח | Vercel (Free) — ראו `vercel.json`; Root Directory = `web` |

## פריסה ל-Vercel

1. ב-vercel.com → **Add New → Project** → יבוא של `ashko/maccabi-app`.
2. **Root Directory** = `web` (Vercel יזהה Vite אוטומטית).
3. Deploy. האפליקציה עובדת מיד עם אחסון מקומי.
4. לסנכרון ענן: **Storage → Create → KV** וחבר לפרויקט (מזריק אוטומטית
   `KV_REST_API_URL` / `KV_REST_API_TOKEN`). ה-endpoint `/api/data` יתחיל לעבוד.

## מבנה

| קובץ | תפקיד |
|------|-------|
| `src/App.tsx` | ה-UI המלא: מתאמנים, אימונים, לו״ז, שליחה, הגדרות |
| `src/lib/domain.ts` | טיפוסים, עזרי זמן ונתוני דוגמה |
| `src/lib/scheduler.ts` | מנוע השיבוץ + מטריצת רכיבה (בצד לקוח) |
| `src/lib/geocode.ts` | חיפוש כתובת (Photon) |
| `src/lib/whatsapp.ts` | בניית הודעה + קישור `wa.me` |
| `src/lib/store.ts` | שמירה ב-`localStorage` |
| `src/components/AddressSearch.tsx` | רכיב חיפוש כתובת עם השלמה |
