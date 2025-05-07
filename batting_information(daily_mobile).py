# mlb_batting_dashboard.py

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import requests
import io
from pybaseball import statcast_batter

st.set_page_config(layout="wide")

# ----------- 데이터 로드 함수 -----------

@st.cache_data
def load_statcast_dataset():
    file_id = "1sWJCEA7MUrOCGfj61ES1JQHJGBfYVYN3"
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(download_url)
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.content.decode("utf-8")))
    df = df[df['game_type'] == 'R']
    df['game_date'] = pd.to_datetime(df['game_date'], errors='coerce')
    df = df.set_index('game_date').sort_index()
    return df

@st.cache_data
def load_batter_id():
    return pd.read_excel('Batter_ID(2025).xlsx')

@st.cache_data
def load_pitcher_id():
    return pd.read_excel('Pitcher_ID(2025).xlsx')


# ----------- 데이터셋 불러오기 -----------

df = load_statcast_dataset()
batter_ID = load_batter_id()
pitcher_ID = load_pitcher_id()

# Batter 이름 병합
df = df.merge(batter_ID, on='batter', how='left')

if df.empty:
    st.error("❌ 데이터셋이 비어있습니다. Google Drive 파일 ID 또는 파일 내용을 확인하세요.")
    st.stop()

# ----------- Streamlit UI -----------

st.title("⚾ MLB 2025 - Daily Batting Info")
st.caption("🧑🏻‍💻 Kyengwook | 📬 kyengwook8@naver.com | [GitHub](https://github.com/kyengwook/kyengwook) | [Instagram](https://instagram.com/kyengwook)")
st.caption("📊 Data: [Baseball Savant](https://baseballsavant.mlb.com/) – MLB 2025 Regular Season")

# Division > Team > Player > Date 선택

divisions = {
    'NL East': ['PHI', 'NYM', 'MIA', 'WSH', 'ATL'],
    'NL Central': ['CHC', 'MIL', 'STL', 'CIN', 'PIT'],
    'NL West': ['LAD', 'SD', 'SF', 'ARI', 'COL'],
    'AL East': ['NYY', 'BOS', 'TOR', 'TB', 'BAL'],
    'AL Central': ['DET', 'KC', 'CLE', 'MIN', 'CWS'],
    'AL West': ['TEX', 'LAA', 'HOU', 'OAK', 'SEA']
}

selected_division = st.selectbox("Select Division", list(divisions.keys()))
selected_team = st.selectbox("Select Team", divisions[selected_division])

# 팀 소속 경기 필터
team_df = df.query(
    "(home_team == @selected_team and inning_topbot == 'Bot') or "
    "(away_team == @selected_team and inning_topbot == 'Top')"
)

if team_df.empty:
    st.warning(f"⚠️ {selected_team} 팀 데이터가 없습니다.")
    st.stop()

# 선수 목록 필터
player_list = sorted(team_df['batter_name'].dropna().unique())
selected_player = st.selectbox("Select Batter", player_list)

player_df = team_df[team_df['batter_name'] == selected_player]
if player_df.empty:
    st.warning(f"⚠️ {selected_player} 선수 데이터가 없습니다.")
    st.stop()

# 날짜 + 상대팀 조합
player_df['opponent_team'] = player_df.apply(
    lambda row: row['away_team'] if row['home_team'] == selected_team else row['home_team'], axis=1
)
player_df['date_team'] = player_df.index.strftime('%Y-%m-%d') + ' vs ' + player_df['opponent_team']

selected_date_str = st.selectbox("Select Date", sorted(player_df['date_team'].unique()))
selected_date = selected_date_str.split(' vs ')[0]
opponent_team = selected_date_str.split(' vs ')[1]

date_df = player_df[player_df.index.strftime('%Y-%m-%d') == selected_date]
if date_df.empty:
    st.warning(f"⚠️ {selected_player}의 {selected_date} 경기 데이터가 없습니다.")
    st.stop()

# ----------- Statcast API 호출 -----------

batter_id = date_df['batter'].iloc[0]
with st.spinner(f"{selected_player}의 Statcast 데이터를 가져오는 중..."):
    statcast_df = statcast_batter(selected_date, selected_date, batter_id)

if statcast_df.empty:
    st.warning(f"⚠️ Statcast에서 {selected_date} 데이터가 없습니다.")
    st.stop()

# 단위 변환 (mph → km/h)
statcast_df['release_speed'] = (statcast_df['release_speed'] * 1.60934).round(1)
statcast_df['launch_speed'] = (statcast_df['launch_speed'] * 1.60934).round(1)

# Pitcher 이름 병합
statcast_df = statcast_df.merge(pitcher_ID, on='pitcher', how='left')

# ----------- 요약 UI -----------

batter_name = statcast_df['player_name'].iloc[0]
st.header(f"{batter_name} — {selected_date} vs {opponent_team}")

# Pitch Details
st.subheader("Pitch Details")
cols_to_show = ['pitch_number', 'pitch_name', 'outs_when_up', 'balls', 'strikes', 'release_speed', 'release_spin_rate', 'type', 'description']
renamed_cols = ['No', 'Type', 'Out', 'B', 'S', 'Velo(km/h)', 'Spin(rpm)', 'Result', 'Desc']
date_df = date_df[cols_to_show]
date_df.columns = renamed_cols
st.dataframe(date_df, hide_index=True)

# ----------- Description 필터 -----------

st.subheader("Batting Info")

desc_options = ['All'] + sorted(statcast_df['description'].dropna().unique())
selected_desc = st.selectbox("Select Description", desc_options)

if selected_desc == 'All':
    desc_df = statcast_df
else:
    desc_df = statcast_df[statcast_df['description'] == selected_desc]

st.dataframe(desc_df)

# ----------- Plotly Strikezone -----------

st.subheader("Pitch Location Chart")

L, R = -0.708333, 0.708333
Bot, Top = 1.5, 3.5

pitch_colors = {
    '4-Seam Fastball': '#D22D49',
    'Sinker': '#FE9D00',
    'Cutter': '#933F2C',
    'Slider': 'darkkhaki',
    'Curveball': 'teal',
    'Changeup': '#1DBE3A',
    'Splitter': '#888888',
    'Other': 'black'
}

scatter_fig = go.Figure()

for pitch in desc_df['pitch_name'].dropna().unique():
    pitch_df = desc_df[desc_df['pitch_name'] == pitch]
    scatter_fig.add_trace(go.Scatter(
        x=pitch_df['plate_x'], y=pitch_df['plate_z'],
        mode='markers+text',
        marker=dict(size=12, color=pitch_colors.get(pitch, 'black')),
        text=pitch_df['pitch_number'], textposition='top center',
        name=pitch
    ))

# 스트라이크존 박스
scatter_fig.add_shape(type='rect', x0=L, x1=R, y0=Bot, y1=Top, line=dict(color='black', width=2))
scatter_fig.update_layout(
    width=550, height=600,
    xaxis=dict(range=[L-1, R+1], showticklabels=False),
    yaxis=dict(range=[Bot-2, Top+2], showticklabels=False),
    showlegend=True, margin=dict(l=10, r=10, t=40, b=10)
)

st.plotly_chart(scatter_fig, use_container_width=True)


