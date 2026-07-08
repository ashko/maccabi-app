# RideCoach 🚴

מערכת אוטומטית לבניית לו״ז אימונים שבועי למאמן כושר ותזונה — שיבוץ חכם של
אימונים קבועים ומשתנים, אופטימיזציית מסלול על אופניים, ושליחת הודעות וואטסאפ
אישיות.

האפיון המלא של המערכת נמצא ב־[`SPEC.md`](./SPEC.md). התיקייה `ridecoach/` היא
מנוע ה־MVP שמדגים את כל השרשרת מקצה־לקצה.

## הרצה מהירה — אפליקציית המאמן

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

זו הדרך המומלצת: קונסולת מאמן מלאה בעברית — ניהול מתאמנים, בניית לו״ז בלחיצה,
תצוגת מפה ושליחת וואטסאפ. רצה **מקומית על המחשב** או ב-**Streamlit Community Cloud**
בעלות אפס. הנתונים נשמרים בקובץ `ridecoach_data.json` והריצה הראשונה נטענת עם
רשימת דוגמה.

### שורת פקודה (לאוטומציה חינמית)

```bash
python weekly_job.py           # מדפיס את לו״ז השבוע הבא
python weekly_job.py --send    # גם שולח הודעות (DRY-RUN ללא חיבור וואטסאפ)
python demo.py                 # הדגמה מלאה על נתוני הדוגמה
```

`weekly_job.py` מתאים ל-cron מקומי חינמי (למשל כל שישי ב-07:00) — ראו הערה בקובץ.
הכול רץ **לגמרי אופליין** כברירת מחדל (מטריצת מרחקים אווירית + שליחה יבשה).

## עלות אפס — למאמן בודד

כל המערכת בנויה על שכבות חינמיות:

| רכיב | פתרון חינמי |
|------|-------------|
| אירוח | הרצה מקומית או Streamlit Community Cloud (חינם) |
| מנוע שיבוץ | OR-Tools — קוד פתוח |
| ניתוב אופניים | OpenRouteService free tier · fallback אווירי ללא מפתח |
| גיאוקודינג | Nominatim (OpenStreetMap) — ללא מפתח |
| אחסון | קובץ JSON מקומי |
| וואטסאפ | WhatsApp Cloud API free tier · ברירת מחדל DRY-RUN |

## מבנה

| קובץ | תפקיד |
|------|-------|
| `streamlit_app.py` | **קונסולת המאמן** — הממשק הראשי |
| `ridecoach/models.py` | מודל הדומיין (מאמן, מתאמן, אימונים, לו״ז) |
| `ridecoach/routing.py` | מטריצת זמני רכיבה — OpenRouteService + fallback אווירי |
| `ridecoach/scheduler.py` | מנוע השיבוץ — VRPTW ב־OR-Tools (״יום = רכב״) + fallback חמדני |
| `ridecoach/messaging.py` | שליחת וואטסאפ — Cloud API + מצב יבש, שליחה אידמפוטנטית |
| `ridecoach/geocode.py` | כתובת ← קואורדינטות (Nominatim/ORS) עם מטמון |
| `ridecoach/storage.py` | אחסון בקובץ JSON |
| `ridecoach/orchestrator.py` | זרימת יום שישי מקצה־לקצה |
| `ridecoach/sample_data.py` | רשימת מתאמנים לדוגמה (תל אביב) |
| `demo.py` · `weekly_job.py` | הרצת הדגמה / ריצה מתוזמנת ללא ממשק |
| `tests/` | חבילת בדיקות (`pytest`) |

## חיבור לספקים אמיתיים

המערכת עוברת אוטומטית לספקים אמיתיים כשמוגדרים משתני סביבה — אין צורך בשינוי קוד:

```bash
export ORS_API_KEY=...            # זמני רכיבה אמיתיים מ-OpenRouteService
export WHATSAPP_TOKEN=...         # WhatsApp Cloud API
export WHATSAPP_PHONE_ID=...
export RIDECOACH_SOLVER_SECONDS=5 # תקציב זמן לסולבר (ברירת מחדל 3)
```

## בדיקות

```bash
RIDECOACH_SOLVER_SECONDS=1 pytest -q
```
