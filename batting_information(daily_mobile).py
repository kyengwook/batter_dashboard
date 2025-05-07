import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import requests
import io
from pybaseball import statcast_batter

# ---- Streamlit config ----
st.set_page_config(page_title="MLB 2025 Daily Batting Info", layout="wide")

# ---- 데이터 로드 함수 ----
@st.cache_data
def load_game_data():
    file_id = "1sWJCEA7MUrOCGfj61ES1JQHJGBfYVYN3"
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(download_url)
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.content.decode("utf-8")), encoding='utf-8')
    df = df[df['game_type'] == 'R']
    df['game_date'] = pd.to_datetime(df['game_date'])
    df = df.set_index('game_date').sort_index()
    return df

@st.cache_data
def load_id_data():
    batter_ID = pd.read_excel('Batter_ID(2025).xlsx')
    pitcher_ID = pd.read_excel('Pitcher_ID(2025).xlsx')
    return batter_ID, pitcher_ID

# ---- 데이터 불러오기 ----
df = load_game_data()
batter_ID, pitcher_ID = load_id_data()

df = pd.merge(df, batter_ID, on='batter', how='left')

if df.empty:
    st.error("❌ 데이터셋이 비어있습니다. Google Drive 파일 ID나 파일 내용을 확인하세요.")
    st.stop()

# ---- 페이지 타이틀 ----
st.title("⚾ MLB 2025 - Daily Batting Info")
st.caption("🧑🏻‍💻 Kyengwook | 📬 kyengwook8@naver.com | [GitHub](https://github.com/kyengwook/kyengwook) | [Instagram](https://instagram.com/kyengwook)")
st.caption("📊 Data: [Baseball Savant](https://baseballsavant.mlb.com/) – MLB 2025 Regular Season")

# ---- Division/Team 선택 ----
divisions = {
    'NL East': ['PHI', 'NYM', 'MIA', 'WSH', 'ATL'],
    'NL Central': ['CHC', 'MIL', 'STL', 'CIN', 'PIT'],
    'NL West': ['LAD', 'SD', 'SF', 'ARI', 'COL'],
    'AL East': ['NYY', 'BOS', 'TOR', 'TB', 'BAL'],
    'AL Central': ['DET', 'KC', 'CLE', 'MIN', 'CWS'],
    'AL West': ['TEX', 'LAA', 'HOU', 'OAK', 'SEA']
}

div_choice = st.selectbox('Select Division', list(divisions.keys()))
team_choice = st.selectbox('Select Team', divisions[div_choice])

# ---- 팀 소속 선수 필터 ----
team_df = df[
    ((df['home_team'] == team_choice) & (df['inning_topbot'] == 'Bot')) |
    ((df['away_team'] == team_choice) & (df['inning_topbot'] == 'Top'))
]

if team_df.empty:
    st.warning(f"⚠️ {team_choice} 팀 데이터가 없습니다.")
    st.stop()

player_list = sorted(team_df['batter_name'].dropna().unique())
player_choice = st.selectbox('Select Batter', player_list)

player_df = team_df[team_df['batter_name'] == player_choice]

# ---- 날짜 선택 ----
player_df['opponent_team'] = player_df.apply(
    lambda row: row['away_team'] if row['home_team'] == team_choice else row['home_team'], axis=1
)
player_df['date_str'] = player_df.index.to_series().dt.strftime('%Y-%m-%d') + ' vs ' + player_df['opponent_team']
date_choice = st.selectbox('Select Date', sorted(player_df['date_str'].unique()))

selected_date = pd.to_datetime(date_choice.split(' vs ')[0])
opponent_team = date_choice.split(' vs ')[1]

daily_df = player_df[player_df.index.normalize() == selected_date]
if daily_df.empty:
    st.warning(f"⚠️ {player_choice} 선수의 {selected_date.date()} 경기 데이터가 없습니다.")
    st.stop()

# ---- Statcast 데이터 ----
batter_id = daily_df['batter'].iloc[0]
statcast_df = statcast_batter(selected_date.strftime('%Y-%m-%d'), selected_date.strftime('%Y-%m-%d'), batter_id)

if statcast_df.empty:
    st.warning(f"⚠️ Statcast 데이터가 없습니다 ({selected_date.date()})")
    st.stop()

statcast_df['release_speed'] = round(statcast_df['release_speed'] * 1.60934, 1)
statcast_df['launch_speed'] = round(statcast_df['launch_speed'] * 1.60934, 1)
statcast_df = pd.merge(statcast_df, pitcher_ID, on='pitcher', how='left')

# ---- Header ----
st.header(f"{player_choice} - {selected_date.date()} vs {opponent_team}")

# ---- Pitch Details ----
st.subheader("Pitch Details")
pitch_df = daily_df.rename(columns={
    'pitch_number': 'No', 'pitch_name': 'Type', 'outs_when_up': 'Out',
    'balls': 'B', 'strikes': 'S', 'release_speed': 'Velo(km/h)',
    'release_spin_rate': 'Spin(rpm)', 'type': 'Result', 'description': 'Desc'
})
st.dataframe(pitch_df[['No', 'Type', 'Out', 'B', 'S', 'Velo(km/h)', 'Spin(rpm)', 'Result', 'Desc']], hide_index=True)

# ---- Batting info ----
st.subheader("Batting Info")
desc_list = ['— Select Description —'] + sorted(statcast_df['description'].dropna().unique())
desc_choice = st.selectbox('Select Description', desc_list)

if desc_choice != '— Select Description —':
    desc_df = statcast_df[statcast_df['description'] == desc_choice]
    st.dataframe(desc_df)

# ---- Plotly Visualization ----
st.subheader("Pitch Location (Strike Zone)")

L, R = -0.708333, 0.708333
Bot, Top = 1.5, 3.5

fig = go.Figure()
pitch_styles = {
    '4-Seam Fastball': '#D22D49', 'Sinker': '#FE9D00', 'Cutter': '#933F2C',
    'Knuckle Curve': 'mediumpurple', 'Sweeper': 'olive', 'Split-Finger': '#888888',
    'Changeup': '#1DBE3A', 'Screwball': '#1DBE3A', 'Forkball': '#888888',
    'Slurve': 'teal', 'Knuckleball': 'lightsteelblue', 'Slider': 'darkkhaki',
    'Curveball': 'teal', 'Eephus': 'black', 'Other': 'black'
}

for pitch, color in pitch_styles.items():
    pdata = statcast_df[statcast_df['pitch_name'] == pitch]
    if pdata.empty:
        continue
    hover = pdata.apply(
        lambda row: f"{row['pitch_name']}<br>{row['release_speed']} km/h<br>{row['description']}<br>{row['events']}<br>xBA {row['estimated_ba_using_speedangle']}" 
        if row['description'] == 'hit_into_play' else
        f"{row['pitch_name']}<br>{row['release_speed']} km/h<br>{row['description']}",
        axis=1
    )
    fig.add_trace(go.Scatter(
        x=pdata['plate_x'], y=pdata['plate_z'],
        mode='markers',
        marker=dict(size=12, color=color),
        text=pdata['pitch_number'], textposition='top center',
        hovertext=hover, name=pitch
    ))

# 스트라이크존 추가
fig.add_shape(type='rect', x0=L, x1=R, y0=Bot, y1=Top, line=dict(color='grey', width=1.5))

fig.update_layout(
    width=550, height=600, showlegend=True,
    title=f"{player_choice} - Pitch Locations ({selected_date.date()})",
    margin=dict(l=5, r=5, t=80, b=5), autosize=True,
    legend=dict(x=0.02, y=0.98, bgcolor='rgba(255,255,255,0.7)', bordercolor='black', borderwidth=1),
    dragmode=False,
    xaxis=dict(range=[L-2.5, R+2.5], showticklabels=False, fixedrange=True),
    yaxis=dict(range=[Bot-3, Top+2], showticklabels=False, fixedrange=True),
)

st.plotly_chart(fig, use_container_width=True)

