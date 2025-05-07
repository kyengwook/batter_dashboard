import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import requests
import io
from pybaseball import statcast_pitcher, statcast_batter

st.set_page_config(layout="wide")

# 데이터 로드 함수
@st.cache_data
def load_data_from_drive():
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
def load_batter_id():
    batter_ID = pd.read_excel('Batter_ID(2025).xlsx')
    return batter_ID

@st.cache_data
def load_pitcher_id():
    pitcher_ID = pd.read_excel('Pitcher_ID(2025).xlsx')
    return pitcher_ID

# 데이터 불러오기
df = load_data_from_drive()
batter_ID = load_batter_id()
pitcher_ID = load_pitcher_id()  # 누락됨 — 꼭 추가!

df = pd.merge(df, batter_ID, on='batter', how='left')

if df.empty:
    st.error("❌ 데이터셋이 비어있습니다. Google Drive 파일 ID나 파일 내용을 확인하세요.")
    st.stop()

st.title("⚾ MLB 2025 - Daily Batting Info")
st.caption("🧑🏻‍💻 Kyengwook | 📬 kyengwook8@naver.com | [GitHub](https://github.com/kyengwook/kyengwook) | [Instagram](https://instagram.com/kyengwook)")
st.caption("📊 Data: [Baseball Savant](https://baseballsavant.mlb.com/) – MLB 2025 Regular Season")

# Division 선택
divisions = {
    'NL East': ['PHI', 'NYM', 'MIA', 'WSH', 'ATL'],
    'NL Central': ['CHC', 'MIL', 'STL', 'CIN', 'PIT'],
    'NL West': ['LAD', 'SD', 'SF', 'AZ', 'COL'],
    'AL East': ['NYY', 'BOS', 'TOR', 'TB', 'BAL'],
    'AL Central': ['DET', 'KC', 'CLE', 'MIN', 'CWS'],
    'AL West': ['TEX', 'LAA', 'HOU', 'ATH', 'SEA']
}

div_options = ['— Select Division —'] + list(divisions.keys())
selected_division = st.selectbox('Division', div_options, label_visibility='collapsed')

if selected_division == '— Select Division —':
    st.info('ℹ️ Division을 먼저 선택해주세요.')
    st.stop()

# 팀 선택
selected_teams = divisions[selected_division]
team_options = ['— Select Team —'] + selected_teams
selected_team = st.selectbox('Team', team_options, label_visibility='collapsed')

if selected_team == '— Select Team —':
    st.info('ℹ️ 팀을 먼저 선택해주세요.')
    st.stop()

# 팀 소속 선수 필터링
team_df = df[
    ((df['home_team'] == selected_team) & (df['inning_topbot'] == 'Bot')) |
    ((df['away_team'] == selected_team) & (df['inning_topbot'] == 'Top'))
]

if team_df.empty:
    st.warning(f"⚠️ {selected_team} 팀 데이터가 없습니다.")
    st.stop()

# 선수 선택
player_options = team_df['batter_name'].dropna().unique()
player_options = ['— Select Batter —'] + sorted(player_options)
selected_player = st.selectbox('Batter', player_options, label_visibility='collapsed')

if selected_player == '— Select Batter —':
    st.info('ℹ️ 선수를 선택해주세요.')
    st.stop()

filtered_player_df = team_df[team_df['batter_name'] == selected_player]

if filtered_player_df.empty:
    st.warning(f"⚠️ {selected_player} 선수 데이터가 없습니다.")
    st.stop()

# 상대팀 정보 추가
filtered_player_df['opponent_team'] = filtered_player_df.apply(
    lambda row: row['away_team'] if row['home_team'] == selected_team else row['home_team'], axis=1
)

# 날짜 + 상대팀 문자열 생성 (예: 2025-04-15 NYM)
# 날짜가 datetime 형식이 아니라면 변환
filtered_player_df.index = pd.to_datetime(filtered_player_df.index, errors='coerce')
filtered_player_df['date_str'] = filtered_player_df.index.to_series().dt.strftime('%Y-%m-%d') + ' ' + filtered_player_df['opponent_team']

# 중복 제거 및 정렬
date_options = ['— Select Date —'] + sorted(filtered_player_df['date_str'].unique())
selected_date_str = st.selectbox('Date', date_options, label_visibility='collapsed')

if selected_date_str == '— Select Date —':
    st.info('ℹ️ 날짜를 선택해주세요.')
    st.stop()

# 선택된 문자열에서 날짜만 추출
selected_date = pd.to_datetime(selected_date_str.split(' ')[0])

# 날짜별 데이터 필터링
filtered_df = filtered_player_df[filtered_player_df.index.normalize() == pd.Timestamp(selected_date)]

if filtered_df.empty:
    st.warning(f"⚠️ {selected_player}의 {selected_date} 날짜 데이터가 없습니다.")
    st.stop()

# batter_id 추출 및 Statcast 데이터 불러오기
batter_id = filtered_df['batter'].iloc[0]
statcast_df = statcast_batter(selected_date.strftime('%Y-%m-%d'), selected_date.strftime('%Y-%m-%d'), batter_id)

# 단위 변환 + Batter ID 병합
statcast_df['release_speed'] = round(statcast_df['release_speed'] * 1.60934, 1)
statcast_df['launch_speed'] = round(statcast_df['launch_speed'] * 1.60934, 1)
statcast_df = pd.merge(statcast_df, pitcher_ID, on='pitcher', how='left')

batter_name = statcast_df['player_name'].iloc[0]

# ---- UI 구분선 ----
opponent_team = selected_date_str.split(' ')[1]
st.header(f"{batter_name} - {selected_date.strftime('%Y-%m-%d')} vs {opponent_team}")

# ---- Pitch Details ----
st.subheader("Pitch Details")

filtered_df = filtered_df.rename(columns={
    'pitch_number': 'No', 'pitch_name': 'Type', 'outs_when_up': 'Out',
    'balls': 'B', 'strikes': 'S', 'release_speed': 'Velo(km/h)',
    'release_spin_rate': 'Spin(rpm)', 'type': 'Result', 'description': 'Desc'
})

st.dataframe(filtered_df[['No', 'Type', 'Out', 'B', 'S', 'Velo(km/h)', 'Spin(rpm)', 'Result', 'Desc']], hide_index=True)

# --- Batting info ---
st.subheader("Batting info")

description_options = statcast_df['description'].dropna().unique()
description_options = ['— Select Description —'] + sorted(description_options)

selected_description = st.selectbox('Description', description_options, label_visibility='collapsed')

if selected_description == '— Select Description —':
    st.info('ℹ️ description 값을 선택해주세요.')
else:
    filtered_df = statcast_df[statcast_df['description'] == selected_description]
    st.dataframe(filtered_df)

# ---- Plotly 시각화 ----
L, R = -0.708333, 0.708333
Bot, Top = 1.5, 3.5

scatter_fig = go.Figure()
pitch_styles = {
    '4-Seam Fastball': {'color': '#D22D49'},
    'Sinker': {'color': '#FE9D00'},
    'Cutter': {'color': '#933F2C'},
    'Knuckle Curve': {'color': 'mediumpurple'},
    'Sweeper': {'color': 'olive'},
    'Split-Finger': {'color': '#888888'},
    'Changeup': {'color': '#1DBE3A'},
    'Screwball': {'color': '#1DBE3A'},
    'Forkball': {'color': '#888888'},
    'Slurve': {'color': 'teal'},
    'Knuckleball': {'color': 'lightsteelblue'},
    'Slider': {'color': 'darkkhaki'},
    'Curveball': {'color': 'teal'},
    'Eephus': {'color': 'black'},
    'Other': {'color': 'black'}
}

for pitch_name, style in pitch_styles.items():
    pitch_data = filtered_df[filtered_df['pitch_name'] == pitch_name]
    if pitch_data.empty:
        continue
    pitch_data = pitch_data.copy()
    pitch_data['custom_hover'] = pitch_data.apply(
        lambda row: f"{row['pitch_name']}<br>{row['release_speed']} km/h<br>{row['description']}<br>{row['events']}<br>xBA {row['estimated_ba_using_speedangle']}" 
        if row['description'] == 'hit_into_play' 
        else f"{row['pitch_name']}<br>{row['release_speed']} km/h<br>{row['description']}",
        axis=1
    )
    scatter_fig.add_trace(
        go.Scatter(
            x=pitch_data['plate_x'], y=pitch_data['plate_z'],
            mode='markers+text', marker=dict(size=13, color=style['color']),
            text=pitch_data['pitch_number'], textposition='top center',
            hovertemplate="%{customdata}<extra></extra>", customdata=pitch_data['custom_hover'], name=pitch_name
        )
    )

# 스트라이크존 추가
scatter_fig.add_shape(type='rect', x0=L, x1=R, y0=Bot, y1=Top, line=dict(color='grey', width=1.5))
scatter_fig.add_shape(type='path', 
    path=f'M {R-0.1},{0} L {L+0.1},{0} L {L-0.1},{-0.6} L 0,{-1.0} L {R+0.1},{-0.6} Z',
    line=dict(color='grey', width=1.5))

scatter_fig.update_layout(
    xaxis=dict(range=[L-2.5, R+2.5], showticklabels=False, fixedrange=True),
    yaxis=dict(range=[Bot-3, Top+2], showticklabels=False, fixedrange=True),
    width=800, height=500, title=f"{selected_player} vs {opponent_team}",
    title_x=0.5, title_y=0.98, plot_bgcolor='white'
)

# 시각화 출력
st.plotly_chart(scatter_fig, use_container_width=True)
