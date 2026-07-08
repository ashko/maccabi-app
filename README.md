# RideCoach 🚴

מערכת אוטומטית לבניית לו״ז אימונים שבועי למאמן כושר ותזונה — שיבוץ חכם של
אימונים קבועים ומשתנים, אופטימיזציית מסלול על אופניים, ושליחת הודעות וואטסאפ
אישיות.

האפיון המלא של המערכת נמצא ב־[`SPEC.md`](./SPEC.md). התיקייה `ridecoach/` היא
מנוע ה־MVP שמדגים את כל השרשרת מקצה־לקצה.

## הרצה מהירה

```bash
pip install -r requirements.txt
python demo.py            # OR-Tools אם מותקן, אחרת הסולבר החמדני
python demo.py greedy     # אילוץ הסולבר החמדני (ללא תלויות)
```

הדמו רץ **לגמרי אופליין** (מטריצת מרחקים אווירית + שליחה יבשה), ומדפיס את הלו״ז
המשובץ לפי ימים כולל זמני רכיבה, ואת הודעות הוואטסאפ שהיו נשלחות.

## מבנה

| קובץ | תפקיד |
|------|-------|
| `ridecoach/models.py` | מודל הדומיין (מאמן, מתאמן, אימונים, לו״ז) |
| `ridecoach/routing.py` | מטריצת זמני רכיבה — OpenRouteService + fallback אווירי |
| `ridecoach/scheduler.py` | מנוע השיבוץ — VRPTW ב־OR-Tools (״יום = רכב״) + fallback חמדני |
| `ridecoach/messaging.py` | שליחת וואטסאפ — Cloud API + מצב יבש, שליחה אידמפוטנטית |
| `ridecoach/orchestrator.py` | זרימת יום שישי מקצה־לקצה |
| `ridecoach/sample_data.py` | רשימת מתאמנים לדוגמה (תל אביב) |
| `demo.py` | הרצת הדגמה מלאה |
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
