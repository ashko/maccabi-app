"""RideCoach — trainer console.

A single free Streamlit app that runs the whole weekly workflow: manage the
roster, generate the bike-optimised schedule, review it on a map, and send the
personalised WhatsApp messages. Runs locally or on Streamlit Community Cloud at
zero cost; falls back gracefully with no API keys.

    streamlit run streamlit_app.py
"""

from __future__ import annotations

import datetime as dt
import os

import pandas as pd
import streamlit as st

from ridecoach.geocode import geocode
from ridecoach.messaging import DryRunSender, default_sender, render_message
from ridecoach.models import (
    CATEGORY_HE,
    WEEKDAYS_HE,
    Category,
    FixedSession,
    FlexibleRequest,
    Location,
    TimeWindow,
    Trainee,
    fmt_hm,
)
from ridecoach.orchestrator import plan_week, send_plan
from ridecoach.storage import Store

WORK_DAYS = [0, 1, 2, 3, 4, 5]  # Sunday..Friday
CAT_OPTIONS = {CATEGORY_HE[c]: c for c in Category}

st.set_page_config(page_title="RideCoach — לו״ז אימונים", page_icon="🚴", layout="wide")

st.markdown("""
<style>
  .stApp { direction: rtl; }
  h1,h2,h3,h4,p,label,div,span,li { direction: rtl; text-align: right; }
  [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { direction: rtl; text-align: right; }
  .stDataFrame, .stTable { direction: ltr; }
  section[data-testid="stSidebar"] { direction: rtl; }
  .day-head { color:#0C6E5D; font-weight:800; font-size:1.05rem; margin:.4rem 0; }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
#  helpers
# --------------------------------------------------------------------------- #

def to_min(t: dt.time) -> int:
    return t.hour * 60 + t.minute


def to_time(m: int) -> dt.time:
    return dt.time(m // 60, m % 60)


@st.cache_resource
def get_store() -> Store:
    return Store()


def refresh() -> None:
    st.cache_resource.clear()
    st.rerun()


store = get_store()


def integration_badge(label: str, ok: bool) -> None:
    st.markdown(f"{'🟢' if ok else '⚪'} {label} — {'מחובר' if ok else 'מצב חינמי/דמו'}")


# --------------------------------------------------------------------------- #
#  sidebar — status + trainer settings
# --------------------------------------------------------------------------- #

with st.sidebar:
    st.markdown("## 🚴 RideCoach")
    st.caption("לו״ז אימונים שבועי · ניתוב אופניים · וואטסאפ")
    st.divider()
    st.markdown("### מצב חיבורים")
    integration_badge("ניתוב (OpenRouteService)", bool(os.environ.get("ORS_API_KEY")))
    integration_badge("וואטסאפ (Cloud API)",
                      bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_ID")))
    st.caption(f"📁 נתונים: `{store.path}`")
    st.divider()

    st.markdown("### ⚙️ הגדרות המאמן")
    tr = store.trainer
    with st.form("trainer_form"):
        home_name = st.text_input("שם/כתובת הבית", tr.home.name)
        c1, c2 = st.columns(2)
        home_lat = c1.number_input("קו רוחב", value=float(tr.home.lat), format="%.5f")
        home_lng = c2.number_input("קו אורך", value=float(tr.home.lng), format="%.5f")
        buffer_min = st.number_input("מרווח בין אימונים (דק׳)", 0, 60, tr.buffer_min, 5)
        max_per_day = st.number_input("מקס׳ אימונים ליום", 1, 12, tr.max_per_day)
        speed = st.number_input("מהירות רכיבה ממוצעת (קמ״ש)", 8.0, 30.0, tr.bike_speed_kmh, 0.5)
        st.caption("שעות עבודה (ריק = יום חופש):")
        new_hours: dict[int, tuple[int, int]] = {}
        for d in WORK_DAYS:
            cur = tr.work_hours.get(d)
            cc = st.columns([1.2, 1, 1])
            active = cc[0].checkbox(WEEKDAYS_HE[d], value=cur is not None, key=f"wd_{d}")
            s = cc[1].time_input("מ-", to_time(cur[0]) if cur else dt.time(8, 0),
                                 key=f"ws_{d}", label_visibility="collapsed", step=900)
            e = cc[2].time_input("עד", to_time(cur[1]) if cur else dt.time(18, 0),
                                 key=f"we_{d}", label_visibility="collapsed", step=900)
            if active:
                new_hours[d] = (to_min(s), to_min(e))
        if st.form_submit_button("💾 שמור הגדרות", width='stretch'):
            tr.home = Location(home_name, home_lat, home_lng)
            tr.buffer_min = int(buffer_min)
            tr.max_per_day = int(max_per_day)
            tr.bike_speed_kmh = float(speed)
            tr.work_hours = new_hours
            store.save()
            st.success("נשמר")


# --------------------------------------------------------------------------- #
#  main tabs
# --------------------------------------------------------------------------- #

st.title("קונסולת המאמן")
tab_people, tab_fixed, tab_flex, tab_plan, tab_send = st.tabs(
    ["👥 מתאמנים", "📌 אימונים קבועים", "🔄 בקשות שבועיות", "🗺️ בניית לו״ז", "💬 שליחה"]
)

# ---- 👥 trainees ---- #
with tab_people:
    st.subheader("מתאמנים")
    if store.trainees:
        df = pd.DataFrame([{
            "שם": t.name, "טלפון": t.phone, "אזור": t.location.name,
            "הסכמה": "✅" if t.consent else "—",
            "lat": round(t.location.lat, 4), "lng": round(t.location.lng, 4),
        } for t in store.trainees])
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.info("אין מתאמנים עדיין — הוסיפו את הראשון למטה.")

    st.markdown("#### הוספה / עריכה")
    names = ["➕ מתאמן חדש"] + [f"{t.name} ({t.id})" for t in store.trainees]
    pick = st.selectbox("בחר", names, key="trainee_pick")
    editing = None if pick.startswith("➕") else store.trainees[names.index(pick) - 1]

    geo_key = "geo_result"
    with st.form("trainee_form"):
        name = st.text_input("שם", editing.name if editing else "")
        phone = st.text_input("טלפון (בפורמט בינ״ל +972...)", editing.phone if editing else "+972")
        addr = st.text_input("כתובת (לחיפוש קואורדינטות)",
                             editing.location.name if editing else "")
        c1, c2 = st.columns(2)
        lat = c1.number_input("קו רוחב", value=float(editing.location.lat) if editing else 32.0705,
                              format="%.5f")
        lng = c2.number_input("קו אורך", value=float(editing.location.lng) if editing else 34.7805,
                              format="%.5f")
        consent = st.checkbox("הסכמה לקבלת הודעות וואטסאפ (Opt-in)",
                              value=editing.consent if editing else False)
        b1, b2, b3 = st.columns(3)
        do_geo = b1.form_submit_button("📍 חפש כתובת", width='stretch')
        do_save = b2.form_submit_button("💾 שמור", width='stretch', type="primary")
        do_del = b3.form_submit_button("🗑️ מחק", width='stretch') if editing else False

    if do_geo:
        loc = geocode(addr)
        if loc:
            st.session_state[geo_key] = loc
            st.success(f"נמצא: {loc.lat:.5f}, {loc.lng:.5f} — לחצו שמור כדי לקבע.")
            lat, lng = loc.lat, loc.lng
        else:
            st.warning("לא נמצאה כתובת — הזינו קואורדינטות ידנית.")
    if do_save:
        if st.session_state.get(geo_key):
            lat, lng = st.session_state[geo_key].lat, st.session_state[geo_key].lng
            st.session_state.pop(geo_key, None)
        loc = Location(addr or name, lat, lng)
        if editing:
            editing.name, editing.phone, editing.location, editing.consent = name, phone, loc, consent
        else:
            store.trainees.append(Trainee(store.next_trainee_id(), name, phone, loc, consent))
        store.save()
        refresh()
    if do_del:
        store.fixed = [f for f in store.fixed if f.trainee.id != editing.id]
        store.flexible = [r for r in store.flexible if r.trainee.id != editing.id]
        store.trainees = [t for t in store.trainees if t.id != editing.id]
        store.save()
        refresh()

# ---- 📌 fixed sessions ---- #
with tab_fixed:
    st.subheader("אימונים קבועים (עוגנים חוזרים)")
    if store.fixed:
        st.dataframe(pd.DataFrame([{
            "מתאמן": f.trainee.name, "אימון": f.label, "סוג": CATEGORY_HE[f.category],
            "יום": WEEKDAYS_HE[f.weekday], "שעה": fmt_hm(f.start),
            "משך": f"{f.duration} דק׳", "אונליין": "💻" if f.is_remote else "—",
        } for f in store.fixed]), width='stretch', hide_index=True)
    else:
        st.info("אין אימונים קבועים.")

    if not store.trainees:
        st.warning("הוסיפו מתאמנים תחילה.")
    else:
        with st.form("fixed_form"):
            st.markdown("#### הוספת אימון קבוע")
            c = st.columns(4)
            tsel = c[0].selectbox("מתאמן", [t.name for t in store.trainees])
            label = c[1].text_input("שם האימון", "כוח")
            cat = c[2].selectbox("סוג", list(CAT_OPTIONS), key="fx_cat")
            dur = c[3].number_input("משך (דק׳)", 15, 180, 60, 15)
            c2 = st.columns(3)
            day = c2[0].selectbox("יום", [WEEKDAYS_HE[d] for d in WORK_DAYS], key="fx_day")
            start = c2[1].time_input("שעה", dt.time(9, 0), step=900, key="fx_start")
            remote = c2[2].checkbox("אונליין", key="fx_remote")
            if st.form_submit_button("➕ הוסף", type="primary"):
                tr_obj = next(t for t in store.trainees if t.name == tsel)
                store.fixed.append(FixedSession(
                    tr_obj, label, CAT_OPTIONS[cat], int(dur),
                    WEEKDAYS_HE.index(day), to_min(start), remote))
                store.save()
                refresh()
        if store.fixed:
            rm = st.selectbox("מחיקת אימון קבוע",
                              ["—"] + [f"{f.trainee.name}: {f.label} ({WEEKDAYS_HE[f.weekday]})"
                                       for f in store.fixed], key="fx_rm")
            if rm != "—" and st.button("🗑️ מחק קבוע"):
                idx = [f"{f.trainee.name}: {f.label} ({WEEKDAYS_HE[f.weekday]})"
                       for f in store.fixed].index(rm)
                store.fixed.pop(idx)
                store.save()
                refresh()

# ---- 🔄 flexible requests ---- #
with tab_flex:
    st.subheader("בקשות שבועיות (לשיבוץ מחדש כל שבוע)")
    if store.flexible:
        st.dataframe(pd.DataFrame([{
            "מתאמן": r.trainee.name, "אימון": r.label, "סוג": CATEGORY_HE[r.category],
            "משך": f"{r.duration} דק׳", "אונליין": "💻" if r.is_remote else "—",
            "חלונות זמינות": " · ".join(
                f"{WEEKDAYS_HE[w.weekday]} {fmt_hm(w.start)}-{fmt_hm(w.end)}"
                for w in r.availability),
        } for r in store.flexible]), width='stretch', hide_index=True)
    else:
        st.info("אין בקשות שבועיות.")

    if not store.trainees:
        st.warning("הוסיפו מתאמנים תחילה.")
    else:
        with st.form("flex_form"):
            st.markdown("#### הוספת בקשה שבועית")
            c = st.columns(4)
            tsel = c[0].selectbox("מתאמן", [t.name for t in store.trainees], key="fl_t")
            label = c[1].text_input("שם האימון", "HIIT", key="fl_l")
            cat = c[2].selectbox("סוג", list(CAT_OPTIONS), key="fl_cat")
            dur = c[3].number_input("משך (דק׳)", 15, 180, 45, 15, key="fl_dur")
            remote = st.checkbox("אונליין (ללא נסיעה)", key="fl_remote")
            st.caption("חלונות זמינות — סמנו ימים והגדירו טווח שעות:")
            windows: list[TimeWindow] = []
            for d in WORK_DAYS:
                cc = st.columns([1.2, 1, 1])
                on = cc[0].checkbox(WEEKDAYS_HE[d], key=f"fl_wd_{d}")
                s = cc[1].time_input("מ-", dt.time(8, 0), step=900,
                                     key=f"fl_ws_{d}", label_visibility="collapsed")
                e = cc[2].time_input("עד", dt.time(13, 0), step=900,
                                     key=f"fl_we_{d}", label_visibility="collapsed")
                if on:
                    windows.append(TimeWindow(d, to_min(s), to_min(e)))
            if st.form_submit_button("➕ הוסף בקשה", type="primary"):
                if not windows:
                    st.error("בחרו לפחות חלון זמינות אחד.")
                else:
                    tr_obj = next(t for t in store.trainees if t.name == tsel)
                    store.flexible.append(FlexibleRequest(
                        tr_obj, label, CAT_OPTIONS[cat], int(dur), windows, remote))
                    store.save()
                    refresh()
        if store.flexible:
            rm = st.selectbox("מחיקת בקשה",
                              ["—"] + [f"{r.trainee.name}: {r.label}" for r in store.flexible],
                              key="fl_rm")
            if rm != "—" and st.button("🗑️ מחק בקשה"):
                idx = [f"{r.trainee.name}: {r.label}" for r in store.flexible].index(rm)
                store.flexible.pop(idx)
                store.save()
                refresh()

# ---- 🗺️ plan ---- #
with tab_plan:
    st.subheader("בניית הלו״ז השבועי")
    c1, c2, c3 = st.columns([1.4, 1, 1])
    # default to next Sunday
    today = dt.date.today()
    days_to_sun = (6 - today.weekday()) % 7 or 7
    default_sun = today + dt.timedelta(days=days_to_sun)
    week = c1.date_input("שבוע שמתחיל ביום ראשון", default_sun)
    prefer = c2.selectbox("סולבר", ["auto", "ortools", "greedy"],
                          help="auto = OR-Tools אם מותקן, אחרת חמדני")
    if c3.button("🧮 בנה לו״ז", type="primary", width='stretch'):
        with st.spinner("מריץ אופטימיזציה..."):
            plan = plan_week(store.trainer, store.fixed, store.flexible,
                             str(week), prefer=prefer)
        st.session_state["plan"] = plan

    plan = st.session_state.get("plan")
    if plan:
        m1, m2, m3 = st.columns(3)
        m1.metric("סה״כ רכיבה בשבוע", f"{plan.total_ride_min} דק׳")
        m2.metric("אימונים ששובצו", len(plan.sessions))
        m3.metric("סולבר", plan.solver.split("-")[0])

        if plan.unscheduled:
            st.error("לא שובצו:")
            for u in plan.unscheduled:
                st.markdown(f"- {u}")

        map_rows = [{"lat": store.trainer.home.lat, "lon": store.trainer.home.lng}]
        for weekday, sessions in plan.by_day().items():
            st.markdown(f"<div class='day-head'>▸ יום {WEEKDAYS_HE[weekday]}</div>",
                        unsafe_allow_html=True)
            rows = []
            for s in sessions:
                rows.append({
                    "שעה": f"{s.start_hm}–{s.end_hm}",
                    "רכיבה": "💻 אונליין" if s.is_remote else f"🚲 {s.travel_from_prev_min} דק׳",
                    "מתאמן": s.trainee.name,
                    "אימון": f"{CATEGORY_HE[s.category]} · {s.label}",
                    "מיקום": "אונליין" if s.is_remote else (s.location.name if s.location else "-"),
                })
                if not s.is_remote and s.location:
                    map_rows.append({"lat": s.location.lat, "lon": s.location.lng})
            st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

        st.markdown("#### מפת העצירות")
        st.map(pd.DataFrame(map_rows), size=60)
        st.caption("הנקודה במרכז = בית המאמן. שאר הנקודות = עצירות פרונטליות בשבוע.")
    else:
        st.info("בחרו שבוע ולחצו \"בנה לו״ז\".")

# ---- 💬 send ---- #
with tab_send:
    st.subheader("שליחת הודעות וואטסאפ")
    plan = st.session_state.get("plan")
    if not plan:
        st.info("בנו לו״ז תחילה (לשונית \"בניית לו״ז\").")
    else:
        wa_ready = bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_ID"))
        st.dataframe(pd.DataFrame([{
            "מתאמן": s.trainee.name, "טלפון": s.trainee.phone,
            "הסכמה": "✅" if s.trainee.consent else "🚫",
            "הודעה": render_message(s),
        } for s in sorted(plan.sessions, key=lambda x: (x.weekday, x.start))]),
            width='stretch', hide_index=True)

        real = st.toggle("שליחה אמיתית (דורש חיבור וואטסאפ)", value=False, disabled=not wa_ready)
        if not wa_ready:
            st.caption("💡 ללא חיבור — כל שליחה תרוץ במצב יבש (DRY-RUN) ולא תישלח בפועל.")
        if st.button("📤 שלח לכל המתאמנים", type="primary"):
            sender = default_sender() if (real and wa_ready) else DryRunSender()
            report = send_plan(plan, sender=sender)
            st.success(f"נשלחו {report.sent} · דולגו {report.skipped} · נכשלו {report.failed}")
            for r in report.results:
                icon = {"sent": "✅", "skipped-no-consent": "🚫",
                        "duplicate": "♻️", "failed": "❌"}.get(r.status, "•")
                st.markdown(f"{icon} **{r.trainee}** — {r.status} · {r.detail}")
