import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from github import Github
import io

# --- [0. 시스템 설정 및 초기화 버튼 (맨 위 배치)] ---
st.set_page_config(page_title="안전보건 대시보드 Pro", layout="wide", page_icon="🛡️")

# CSS
st.markdown("""
<style>
    div[data-testid="stMetricValue"] {font-size: 24px; font-weight: bold; color: #31333F;}
    .stButton > button {width: 100%; border-radius: 6px;}
</style>
""", unsafe_allow_html=True)

st.title("🛡️ 산업안전보건 통합 관리 시스템")

# ▼▼▼▼▼ 여기가 안 보이면 코드가 반영 안 된 것입니다 ▼▼▼▼▼
with st.sidebar:
    st.header("🚨 긴급 복구 메뉴")
    if st.button("🔥 시스템 완전 초기화 (누르면 고쳐짐)", type="primary"):
        st.session_state.clear()
        st.rerun()
    st.markdown("---")
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

# ==========================================
# [설정] 특별교육 옵션 (4번, 35번, 해당없음)
# ==========================================
SPECIAL_EDU_OPTIONS = [
    "해당없음",
    "4. 폭발성·물반응성·자기반응성·자기발열성 물질, 자연발화성 액체·고체 및 인화성 액체의 제조 또는 취급작업",
    "35. 허가 및 관리 대상 유해물질의 제조 또는 취급작업"
]

def sanitize_config_df(df):
    target_cols = ['특별교육과목1', '특별교육과목2']
    for col in target_cols:
        if col not in df.columns: df[col] = "해당없음"
    for col in target_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].apply(lambda x: x if x in SPECIAL_EDU_OPTIONS else "해당없음")
    if '유해인자' not in df.columns: df['유해인자'] = "없음"
    else: df['유해인자'] = df['유해인자'].fillna("없음")
    return df

# ==========================================
# [GitHub 설정]
# ==========================================
with st.sidebar:
    st.header("⚙️ GitHub 설정")
    GITHUB_TOKEN = st.text_input("🔑 GitHub 토큰", type="password")
    REPO_NAME = st.text_input("📂 레포지토리 (user/repo)")
    DATA_FILE = "data.csv"
    CONFIG_FILE = "config.csv"

def get_github_repo():
    if not GITHUB_TOKEN or not REPO_NAME: return None
    try: return Github(GITHUB_TOKEN).get_repo(REPO_NAME)
    except: return None

def save_all_to_github(data_df, config_df):
    repo = get_github_repo()
    if not repo: 
        st.sidebar.error("토큰 확인 필요")
        return
    try:
        data_content = data_df.to_csv(index=False)
        try:
            contents = repo.get_contents(DATA_FILE)
            repo.update_file(DATA_FILE, f"Update data: {datetime.now()}", data_content, contents.sha)
        except:
            repo.create_file(DATA_FILE, "Init data", data_content)
        
        config_content = config_df.to_csv(index=False)
        try:
            contents = repo.get_contents(CONFIG_FILE)
            repo.update_file(CONFIG_FILE, f"Update config: {datetime.now()}", config_content, contents.sha)
        except:
            repo.create_file(CONFIG_FILE, "Init config", config_content)
        st.toast("✅ 저장 완료!", icon="☁️")
    except Exception as e:
        st.sidebar.error(f"저장 실패: {e}")

def load_all_from_github():
    repo = get_github_repo()
    if not repo: return None, None
    loaded_data, loaded_config = None, None
    try:
        contents = repo.get_contents(DATA_FILE)
        csv_string = contents.decoded_content.decode("utf-8")
        loaded_data = pd.read_csv(io.StringIO(csv_string))
        for col in ['입사일', '최근_직무교육일', '최근_특수검진일']:
            if col in loaded_data.columns:
                loaded_data[col] = pd.to_datetime(loaded_data[col].astype(str), errors='coerce').dt.date
    except: pass
    try:
        contents = repo.get_contents(CONFIG_FILE)
        csv_string = contents.decoded_content.decode("utf-8")
        loaded_config = pd.read_csv(io.StringIO(csv_string))
        loaded_config = sanitize_config_df(loaded_config)
    except: pass
    return loaded_data, loaded_config

# --- [2. 부서 설정] ---
if 'dept_config' not in st.session_state:
    st.session_state.dept_config = pd.DataFrame({
        '정렬순서': [1, 2, 3, 4],
        '부서명': ['용접팀', '전기팀', '밀폐작업팀', '일반관리팀'],
        '특별교육과목1': ["해당없음"] * 4, '특별교육과목2': ["해당없음"] * 4,
        '유해인자': ['용접흄, 분진', '전류(감전)', '산소결핍', '없음']
    })
# [강제 적용]
st.session_state.dept_config = sanitize_config_df(st.session_state.dept_config)

with st.expander("🛠️ [관리자 설정] 부서 및 교육 매핑"):
    with st.popover("📂 부서 일괄 등록 (Excel/CSV)"):
        dept_file = st.file_uploader("파일 선택", type=['csv', 'xlsx'])
        if dept_file:
            try:
                if dept_file.name.endswith('.csv'): new_d = pd.read_csv(dept_file)
                else: new_d = pd.read_excel(dept_file)
                if st.button("부서 등록"):
                    if '부서명' not in new_d.columns: st.error("부서명 컬럼 없음")
                    else:
                        new_d = new_d.rename(columns={'특별교육 1':'특별교육과목1', '특별교육 2':'특별교육과목2'})
                        new_d = sanitize_config_df(new_d)
                        cols = ['부서명', '특별교육과목1', '특별교육과목2', '유해인자']
                        for c in cols: 
                            if c not in new_d.columns: new_d[c] = "해당없음" if "특별" in c else "없음"
                        final_d = pd.concat([st.session_state.dept_config[cols], new_d[cols]]).drop_duplicates(['부서명'], keep='last').reset_index(drop=True)
                        final_d.insert(0, '정렬순서', range(1, len(final_d)+1))
                        st.session_state.dept_config = final_d
                        st.rerun()
            except Exception as e: st.error(str(e))

    st.markdown("#### 매핑 상세 설정")
    df_c = st.session_state.dept_config.sort_values('정렬순서')
    edited_c = st.data_editor(
        df_c, key="d_edit", hide_index=True, num_rows="dynamic", use_container_width=True,
        column_config={
            "특별교육과목1": st.column_config.SelectboxColumn("특별교육1", options=SPECIAL_EDU_OPTIONS),
            "특별교육과목2": st.column_config.SelectboxColumn("특별교육2", options=SPECIAL_EDU_OPTIONS)
        }
    )
    if not df_c.equals(edited_c): st.session_state.dept_config = edited_c

    DEPT_S1 = dict(zip(st.session_state.dept_config['부서명'], st.session_state.dept_config['특별교육과목1']))
    DEPT_S2 = dict(zip(st.session_state.dept_config['부서명'], st.session_state.dept_config['특별교육과목2']))
    DEPT_FAC = dict(zip(st.session_state.dept_config['부서명'], st.session_state.dept_config['유해인자']))
    DEPTS = list(st.session_state.dept_config['부서명'])

# --- [3. 데이터 초기화] ---
ROLES = ["안전보건관리책임자", "관리감독자", "폐기물담당자", "일반근로자"]
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame({
        '성명': ['김철수', '이영희', '박신규', '강폐기'],
        '직책': ['안전보건관리책임자', '관리감독자', '일반근로자', '폐기물담당자'],
        '부서': ['일반관리팀', '일반관리팀', '용접팀', '일반관리팀'],
        '입사일': [date(2022,1,1), date(2023,5,20), date.today(), date(2020,1,1)],
        '최근_직무교육일': [date(2023,5,1), date(2024,5,20), None, date(2022,5,1)],
        '신규교육_이수': [False]*4, '특별_공통_8H': [False]*4,
        '검진단계': ['배치전(미실시)']*4, '최근_특수검진일': [None]*4, 
        '특수검진_대상': [True, True, True, False]
    })

# [필수 컬럼 보장]
req_cols = ['퇴사여부', '신규교육_이수', '특수검진_대상', '특별_공통_8H', '특별_1_이론_4H', '특별_1_실습_4H', '특별_2_이론_4H', '특별_2_실습_4H']
for c in req_cols:
    if c not in st.session_state.df.columns:
        st.session_state.df[c] = True if c == '특수검진_대상' else False

# --- [4. 계산 로직] ---
df = st.session_state.df.copy()
today = date.today()

for c in ['입사일', '최근_직무교육일', '최근_특수검진일']:
    if c in df.columns: df[c] = pd.to_datetime(df[c].astype(str), errors='coerce').dt.date

df['특별교육_과목1'] = df['부서'].map(DEPT_S1).fillna("설정필요")
df['특별교육_과목2'] = df['부서'].map(DEPT_S2).fillna("해당없음")
df['유해인자'] = df['부서'].map(DEPT_FAC).fillna("확인필요")
df['입사연도'] = pd.to_datetime(df['입사일'].astype(str)).dt.year
df['법적_신규자'] = pd.to_datetime(df['입사일'].astype(str)).apply(lambda x: (pd.Timestamp(today)-x).days < 90)

def add_days(d, days):
    try: return d + timedelta(days=days)
    except: return None

# [직무교육 계산]
df['다음_직무교육일'] = None
df.loc[df['직책']=='안전보건관리책임자', '다음_직무교육일'] = df['최근_직무교육일'].apply(lambda x: add_days(x, 730))
df.loc[df['직책']=='관리감독자', '다음_직무교육일'] = df['최근_직무교육일'].apply(lambda x: add_days(x, 365))
# [수정: 폐기물 3년]
df.loc[df['직책'].astype(str).str.strip()=='폐기물담당자', '다음_직무교육일'] = df['최근_직무교육일'].apply(lambda x: add_days(x, 1095))

# [검진일 계산]
def calc_health(row):
    if not row.get('특수검진_대상', True): return None # 체크해제시 제외
    if row['검진단계'] == '배치전(미실시)' or pd.isna(row['최근_특수검진일']): return None
    cycle = 180 if row['검진단계'] == "1차검진 완료(다음:6개월)" else 365
    return add_days(row['최근_특수검진일'], cycle)
df['다음_특수검진일'] = df.apply(calc_health, axis=1)

dash_df = df[df['퇴사여부']==False]

# --- [5. 대시보드] ---
c1,c2,c3,c4 = st.columns(4)
c1.metric("총 인원", f"{len(dash_df)}명")
c2.metric("신규 입사", f"{len(dash_df[dash_df['법적_신규자']])}명")
c3.metric("책임자/감독자", f"{len(dash_df[dash_df['직책'].isin(['안전보건관리책임자','관리감독자'])])}명")
c4.metric("검진 대상", f"{len(dash_df[dash_df['특수검진_대상']==True])}명")

st.divider()

# --- [사이드바 저장] ---
with st.sidebar:
    if st.button("💾 저장하기", type="primary"):
        save_all_to_github(st.session_state.df, st.session_state.dept_config)
    with st.expander("📂 명부 등록"):
        up_file = st.file_uploader("파일", type=['csv','xlsx'], key="main_up")
        if up_file:
            try:
                new_df = pd.read_csv(up_file) if up_file.name.endswith('.csv') else pd.read_excel(up_file)
                if st.button("병합"):
                    if '성명' not in new_df.columns: st.error("성명 없음")
                    else:
                        for c in st.session_state.df.columns:
                            if c not in new_df.columns: new_df[c] = None
                        if '특수검진_대상' in new_df.columns:
                            new_df['특수검진_대상'] = new_df['특수검진_대상'].fillna(True).astype(bool)
                        else: new_df['특수검진_대상'] = True
                        
                        st.session_state.df = pd.concat([st.session_state.df, new_df[st.session_state.df.columns]], ignore_index=True)
                        st.rerun()
            except Exception as e: st.error(str(e))

st.markdown("### 📝 근로자 정보 수정 (특수검진 체크 해제 시 제외됨)")
edited_main = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True, key="main_ed",
    column_config={"특수검진_대상": st.column_config.CheckboxColumn("검진대상", default=True), "입사일": st.column_config.DateColumn(format="YYYY-MM-DD")})
if not st.session_state.df.equals(edited_main): st.session_state.df = edited_main

# --- [탭 뷰] ---
t1, t2, t3, t4, t5 = st.tabs(["책임자/감독자", "폐기물 담당자", "신규 입사자", "특별교육", "특수검진"])

def show_tab(tab, sub_df, key, cols_cfg):
    with tab:
        if sub_df.empty: st.info("대상자 없음")
        else:
            sub_df = sub_df.reset_index(drop=True)
            sub_df.insert(0, "No", sub_df.index+1)
            ed = st.data_editor(sub_df, key=key, hide_index=True, use_container_width=True, column_config=cols_cfg, disabled=["No"])
            # 데이터 업데이트 (No 제외)
            real_ed = ed.drop(columns=["No"])
            origin_cols = sub_df.drop(columns=["No"]).columns
            # 변경 감지 시 원본 df 업데이트 로직 생략(간소화) - 메인 에디터 사용 권장

# 1. 책임자
sub = dash_df[dash_df['직책'].isin(['안전보건관리책임자', '관리감독자'])].copy()
if not sub.empty: sub['상태'] = sub.apply(lambda x: "🔴 초과" if pd.isna(x['다음_직무교육일']) or (x['다음_직무교육일']-today).days<0 else "🟢 양호", axis=1)
show_tab(t1, sub[['성명','직책','최근_직무교육일','다음_직무교육일','상태']], "t1", {"다음_직무교육일": st.column_config.DateColumn()})

# 2. 폐기물
sub = dash_df[dash_df['직책'].astype(str).str.strip()=='폐기물담당자'].copy()
if not sub.empty: sub['상태'] = sub.apply(lambda x: "🔴 초과" if pd.isna(x['다음_직무교육일']) or (x['다음_직무교육일']-today).days<0 else "🟢 양호", axis=1)
show_tab(t2, sub[['성명','부서','최근_직무교육일','다음_직무교육일','상태']], "t2", {"다음_직무교육일": st.column_config.DateColumn()})

# 3. 신규 (3개년)
with t3:
    y_opts = [today.year, today.year-1, today.year-2]
    sel_y = st.radio("입사년도", y_opts, horizontal=True)
    sub = dash_df[dash_df['입사연도']==sel_y].copy()
    show_tab(t3, sub[['신규교육_이수','성명','입사일','부서']], "t3", {})

# 4. 특별교육
sub = dash_df[dash_df['특별교육_과목1']!='해당없음'].copy()
show_tab(t4, sub[['성명','부서','특별교육_과목1','특별_공통_8H','특별_1_이론_4H','특별_1_실습_4H']], "t4", {})

# 5. 특수검진 (체크된 사람만)
sub = dash_df[dash_df['특수검진_대상']==True].copy()
if not sub.empty: sub['상태'] = sub.apply(lambda x: "🔴 필요" if x['검진단계']=='배치전(미실시)' else ("🟢 양호" if pd.notnull(x['다음_특수검진일']) and (x['다음_특수검진일']-today).days>0 else "🔴 초과"), axis=1)
show_tab(t5, sub[['성명','부서','유해인자','검진단계','최근_특수검진일','다음_특수검진일','상태']], "t5", {})
