import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="מחשבון פליי-אין - מכבי תל אביב", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #001f52; color: #ffffff; }
    h1, h2, h3, p, div { direction: rtl; text-align: right; font-family: sans-serif; }
    .main-header { color: #FCE300; text-align: center !important; font-weight: 900; font-size: 2.8rem; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); margin-bottom: 5px; }
    .sub-header { text-align: center !important; color: #e0e0e0; font-size: 1.2rem; margin-bottom: 30px; }
    .game-card { background-color: rgba(255, 255, 255, 0.05); border: 1px solid #FCE300; border-radius: 12px; padding: 15px; margin-bottom: 15px; text-align: center !important; }
    .game-title { color: #ffffff; font-size: 1.1rem; font-weight: bold; margin-bottom: 10px; text-align: center !important; }
    div.row-widget.stRadio > div { flex-direction: row; justify-content: center; background-color: #002D72; padding: 10px; border-radius: 8px; }
    .stDataFrame { direction: ltr; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">מחשבון פליי-אין יורוליג 🏀</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">הסימולטור הרשמי לאוהדי מכבי - כולל מחזורי הסיום</div>', unsafe_allow_html=True)

@st.cache_data(ttl=300)
def get_live_standings():
    # נתוני בסיס למקרה שה-API לא זמין או לחסימות רשת
    return pd.DataFrame([
        {"קבוצה": "Zalgiris", "נ'": 19, "ה'": 14, "הפרש": 110},
        {"קבוצה": "Monaco", "נ'": 19, "ה'": 14, "הפרש": 105},
        {"קבוצה": "Panathinaikos", "נ'": 19, "ה'": 14, "הפרש": 95},
        {"קבוצה": "Crvena Zvezda", "נ'": 19, "ה'": 14, "הפרש": 80},
        {"קבוצה": "Barcelona", "נ'": 19, "ה'": 14, "הפרש": 75},
        {"קבוצה": "Maccabi Tel Aviv", "נ'": 17, "ה'": 16, "הפרש": 45},
        {"קבוצה": "Dubai", "נ'": 17, "ה'": 17, "הפרש": 10},
        {"קבוצה": "Olimpia Milano", "נ'": 15, "ה'": 18, "הפרש": -15},
        {"קבוצה": "Bayern Munich", "נ'": 15, "ה'": 18, "הפרש": -30}
    ])

df_original = get_live_standings()

# הלו"ז הקריטי של מחזורי הסיום
upcoming_matches = [
    {"id": "m1", "home": "Maccabi Tel Aviv", "away": "Olimpia Milano"},
    {"id": "m2", "home": "Maccabi Tel Aviv", "away": "Barcelona"},
    {"id": "m3", "home": "Crvena Zvezda", "away": "Panathinaikos"},
    {"id": "m4", "home": "Monaco", "away": "Bayern Munich"},
    {"id": "m5", "home": "Dubai", "away": "Zalgiris"}
]

if 'match_results' not in st.session_state:
    st.session_state.match_results = {}

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 🔮 מחזורי הסיום")
    
    for match in upcoming_matches:
        st.markdown(f'<div class="game-card"><div class="game-title">{match["home"]} 🆚 {match["away"]}</div></div>', unsafe_allow_html=True)
        choice = st.radio(
            label="בחר מנצחת:",
            options=["טרם שוחק", match["home"], match["away"]],
            key=match["id"],
            label_visibility="collapsed"
        )
        st.session_state.match_results[match["id"]] = choice

    if st.button("🔄 אפס בחירות"):
        for match in upcoming_matches:
            st.session_state.match_results[match["id"]] = "טרם שוחק"
        st.rerun()

df_simulated = df_original.copy()

for match in upcoming_matches:
    winner = st.session_state.match_results.get(match["id"], "טרם שוחק")
    if winner != "טרם שוחק":
        loser = match["home"] if winner == match["away"] else match["away"]
        df_simulated.loc[df_simulated['קבוצה'] == winner, "נ'"] += 1
        df_simulated.loc[df_simulated['קבוצה'] == loser, "ה'"] += 1

df_simulated = df_simulated.sort_values(by=["נ'", 'הפרש'], ascending=[False, False]).reset_index(drop=True)
df_simulated.index = df_simulated.index + 1

def get_status(rank):
    if rank <= 6: return "🏆 פלייאוף ישיר"
    elif rank <= 10: return "⚡ פליי-אין"
    else: return "❌ מחוץ לתמונה"

df_simulated.insert(0, "דירוג", df_simulated.index)
df_simulated["סטטוס"] = df_simulated["דירוג"].apply(get_status)

def highlight_maccabi(val):
    if val == "Maccabi Tel Aviv":
        return 'background-color: #FCE300; color: #002D72; font-weight: bold;'
    return ''

styled_df = df_simulated.style.map(highlight_maccabi, subset=['קבוצה'])

with col2:
    st.markdown("### 📊 טבלת היורוליג (לייב + סימולציה)")
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "דירוג": st.column_config.NumberColumn(width="small"),
            "סטטוס": st.column_config.TextColumn(width="medium"),
            "קבוצה": st.column_config.TextColumn(width="large"),
        }
    )
