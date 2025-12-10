import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from github import Github
import io

# --- [1. 시스템 설정] ---
st.set_page_config(page_title="안전보건 대시보드 Pro", layout="wide", page_icon="🛡️")

# CSS: 디자인 및 안정성
st.markdown("""
<style>
    div[data-testid="stMetricValue"] {font-size: 24px; font-weight: bold; color: #31333F;}
    div.stButton > button {width: 100%; border-radius: 6px;}
</style>
""", unsafe_allow_html=True)

st.title("🛡️ 산업안전보건 통합 관리 시스템")
st.markdown("---")

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
    st.header("⚙️ 시스템 설정")
    # [긴급] 캐시 문제 해결을 위한 초기화 버튼
    if st.button("🔄 데이터 강제 새로고침", type="primary"):
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()
        
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
# [강제 적용] 변수명을 dept_config_v1으로 바꿔서 강제 로드 유도
if 'dept_config_v1' not in st.session_state:
    st.session_state.dept_config_v1 = pd.DataFrame({
        '정렬순서': [1, 2, 3, 4],
        '부서명': ['용접팀', '전기팀', '밀폐작업팀', '일반관리팀'],
        '특별교육과목1': ["해당없음"] * 4, '특별교육과목2': ["해당없음"] * 4,
        '유해인자': ['용접흄, 분진', '전류(감전)', '산소결핍', '없음']
    })
# 매번 강제 정화
st.session_state.dept_config_v1 = sanitize_config_df(st.session_state.dept_config_v1)

with st.expander("🛠️ [관리자 설정] 부서 및 교육 매핑"):
    sorted_df = st.session_state.dept_config_v1.sort_values('정렬순서')
    edited_dept_config = st.data_editor(
        sorted_df, num_rows="dynamic", key="dept_editor", use_container_width=True, hide_index=True,
        column_config={
            "특별교육과목1": st.column_config.SelectboxColumn("특별교육 1", width="large", options=SPECIAL_EDU_OPTIONS),
            "특별교육과목2": st.column_config.SelectboxColumn("특별교육 2", width="large", options=SPECIAL_EDU_OPTIONS),
        }
    )
    if not sorted_df.equals(edited_dept_config):
        st.session_state.dept_config_v1 = edited_dept_config

    DEPT_S1 = dict(zip(st.session_state.dept_config_v1['부서명'], st.session_state.dept_config_v1['특별교육과목1']))
    DEPT_S2 = dict(zip(st.session_state.dept_config_v1['부서명'], st.session_state.dept_config_v1['특별교육과목2']))
    DEPT_FAC = dict(zip(st.session_state.dept_config_v1['부서명'], st.session_state.dept_config_v1['유해인자']))
    DEPTS_LIST = list(st.session_state.dept_config_v1['부서명'])

# --- [3. 메인 데이터 초기화 (변수명 변경으로 강제 리셋)] ---
ROLES = ["안전보건관리책임자", "관리감독자", "폐기물담당자", "일반근로자"]
HEALTH_PHASES = ["배치전(미실시)", "1차검진 완료(다음:6개월)", "정기검진(다음:1년)"]

# [핵심] 변수명을 df_new_v1으로 변경하여 기존 캐시 무시함
if 'df_new_v1' not in st.session_state:
    data = {
        '성명': ['김철수', '이영희', '박신규', '최신규', '정전기', '강폐기'],
        '직책': ['안전보건관리책임자', '관리감독자', '일반근로자', '일반근로자', '일반근로자', '폐기물담당자'],
        '부서': ['일반관리팀', '일반관리팀', '용접팀', '용접팀', '전기팀', '일반관리팀'],
        '입사일': [date(2022, 1, 1), date(2023, 5, 20), date.today(), date(2020, 1, 1), date(2023, 6, 1), date(2020, 1, 1)],
        '최근_직무교육일': [date(2023, 5, 1), date(2024, 5, 20), None, None, None, date(2022, 5, 1)],
        '신규교육_이수': [False, False, False, False, False, False],
        '특별_공통_8H': [False, False, False, False, True, False],
        '검진단계': ['배치전(미실시)', '배치전(미실시)', '배치전(미실시)', '배치전(미실시)', '1차검진 완료(다음:6개월)', '배치전(미실시)'], 
        '최근_특수검진일': [None, None, None, None, date(2024, 12, 1), None],
        '특수검진_대상': [True, True, True, True, True, False] 
    }
    st.session_state.df_new_v1 = pd.DataFrame(data)

# [강제 보정] 특수검진_대상 컬럼이 없으면 무조건 생성
if '특수검진_대상' not in st.session_state.df_new_v1.columns:
    st.session_state.df_new_v1['특수검진_대상'] = True

required_columns = ['퇴사여부', '신규교육_이수', '특별_공통_8H', '특별_1_이론_4H', '특별_1_실습_4H', '특별_2_이론_4H', '특별_2_실습_4H']
for col in required_columns:
    if col not in st.session_state.df_new_v1.columns:
        st.session_state.df_new_v1[col] = False

# --- [4. 계산 로직 (매번 실행)] ---
df = st.session_state.df_new_v1.copy()
today = date.today()

for col in ['입사일', '최근_직무교육일', '최근_특수검진일']:
    if col in df.columns: df[col] = pd.to_datetime(df[col].astype(str), errors='coerce').dt.date

df['특별교육_과목1'] = df['부서'].map(DEPT_S1).fillna("설정필요")
df['특별교육_과목2'] = df['부서'].map(DEPT_S2).fillna("해당없음")
df['유해인자'] = df['부서'].map(DEPT_FAC).fillna("확인필요")

# [중요] 유해인자 없음 -> 특수검진 자동 해제 로직 (원하시면 주석 해제)
# df.loc[df['유해인자'] == '없음', '특수검진_대상'] = False

def add_days(d, days):
    try: return d + timedelta(days=days)
    except: return None

df['입사일_dt'] = pd.to_datetime(df['입사일'].astype(str), errors='coerce')
df['입사연도'] = df['입사일_dt'].dt.year
df['법적_신규자'] = df['입사일_dt'].apply(lambda x: (pd.Timestamp(today) - x).days < 90 if pd.notnull(x) else False)

df['다음_직무교육일'] = None
df.loc[df['직책']=='안전보건관리책임자', '다음_직무교육일'] = df['최근_직무교육일'].apply(lambda x: add_days(x, 730))
df.loc[df['직책']=='관리감독자', '다음_직무교육일'] = df['최근_직무교육일'].apply(lambda x: add_days(x, 365))

# [확인 완료] 폐기물 담당자 3년(1095일) 계산
mask_waste = df['직책'].astype(str).str.strip() == '폐기물담당자'
df.loc[mask_waste, '다음_직무교육일'] = df[mask_waste]['최근_직무교육일'].apply(lambda x: add_days(x, 1095))

def calc_next_health(row):
    # [확인 완료] 특수검진 대상 미체크(False)시 계산 안함
    if not row.get('특수검진_대상', True): return None 
    if row['검진단계'] == "배치전(미실시)" or pd.isna(row['최근_특수검진일']): return None
    cycle = 180 if row['검진단계'] == "1차검진 완료(다음:6개월)" else 365
    return add_days(row['최근_특수검진일'], cycle)

df['다음_특수검진일'] = df.apply(calc_next_health, axis=1)
dashboard_df = df[df['퇴사여부'] == False]

col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("👥 총 관리 인원", f"{len(dashboard_df)}명")
with col2: st.metric("🌱 신규 입사자", f"{len(dashboard_df[dashboard_df['법적_신규자']])}명")
with col3: st.metric("👔 책임자/감독자", f"{len(dashboard_df[dashboard_df['직책'].isin(['안전보건관리책임자', '관리감독자'])])}명")
with col4: st.metric("🏥 검진 대상", f"{len(dashboard_df[dashboard_df['특수검진_대상'] == True])}명")

st.divider()

# --- [5. 데이터 입력 및 저장] ---
with st.sidebar:
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📂 불러오기"):
            ld, lc = load_all_from_github()
            if ld is not None: st.session_state.df_new_v1 = ld
            if lc is not None: st.session_state.dept_config_v1 = lc
            st.rerun()
    with c2:
        if st.button("💾 저장하기", type="primary"):
            save_all_to_github(st.session_state.df_new_v1, st.session_state.dept_config_v1)
    
    with st.expander("📂 명부 일괄 등록"):
        up_file = st.file_uploader("파일", type=['csv', 'xlsx'])
        if up_file:
            try:
                new_df = pd.read_csv(up_file) if up_file.name.endswith('.csv') else pd.read_excel(up_file)
                if st.button("병합"):
                    if '성명' not in new_df.columns: st.error("성명 컬럼 필수")
                    else:
                        for c in st.session_state.df_new_v1.columns:
                            if c not in new_df.columns: new_df[c] = None
                        if '특수검진_대상' in new_df.columns:
                            new_df['특수검진_대상'] = new_df['특수검진_대상'].fillna(True).astype(bool)
                        else: new_df['특수검진_대상'] = True
                        st.session_state.df_new_v1 = pd.concat([st.session_state.df_new_v1, new_df[st.session_state.df_new_v1.columns]], ignore_index=True)
                        st.rerun()
            except Exception as e: st.error(str(e))

st.markdown("### 📝 근로자 명부 수정")
st.caption("특수검진 대상이 아닌 경우 '검진대상' 체크를 해제하세요. (저장 시 탭에서 사라짐)")

# [확인 완료] 특수검진 대상 체크박스 제공
edited_df = st.data_editor(
    st.session_state.df_new_v1,
    num_rows="dynamic",
    use_container_width=True,
    key="main_editor",
    column_config={
        "퇴사여부": st.column_config.CheckboxColumn("퇴사", default=False, width="small"),
        "특수검진_대상": st.column_config.CheckboxColumn("검진대상", default=True, width="small"),
        "입사일": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "최근_직무교육일": st.column_config.DateColumn(),
        "검진단계": None, "최근_특수검진일": None
    }
)
if not st.session_state.df_new_v1.equals(edited_df):
    st.session_state.df_new_v1 = edited_df

# --- [6. 탭 화면] ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["👔 책임자/감독자", "♻️ 폐기물 담당자", "🌱 신규 입사자", "⚠️ 특별교육", "🏥 특수건강검진"])

def safe_update(sub_df, key, cols):
    sub_df = sub_df.reset_index(drop=True)
    sub_df.insert(0, "No", sub_df.index+1)
    st.data_editor(sub_df, key=key, hide_index=True, use_container_width=True, column_config=cols, disabled=["No"])
    # 부분 업데이트는 메인 에디터 사용 권장 (복잡도 방지)

with tab1:
    target = dashboard_df[dashboard_df['직책'].isin(['안전보건관리책임자', '관리감독자'])].copy()
    if not target.empty:
        target['상태'] = target.apply(lambda r: "🔴 초과" if pd.isna(r['다음_직무교육일']) or (r['다음_직무교육일']-today).days<0 else "🟢 양호", axis=1)
        safe_update(target[['성명','직책','최근_직무교육일','다음_직무교육일','상태']], "t1", {"다음_직무교육일": st.column_config.DateColumn()})
    else: st.info("대상자 없음")

with tab2:
    # [확인 완료] 폐기물 담당자
    target = dashboard_df[dashboard_df['직책'].astype(str).str.strip() == '폐기물담당자'].copy()
    if not target.empty:
        target['상태'] = target.apply(lambda r: "🔴 필요" if pd.isna(r['최근_직무교육일']) else ("🔴 초과" if (r['다음_직무교육일']-today).days<0 else "🟢 양호"), axis=1)
        safe_update(target[['성명','부서','최근_직무교육일','다음_직무교육일','상태']], "t2", {"다음_직무교육일": st.column_config.DateColumn()})
    else: st.info("대상자 없음")

with tab3:
    # [확인 완료] 3개년 조회 (올해, 작년, 재작년)
    years = [today.year, today.year-1, today.year-2]
    sel_y = st.radio("입사년도 선택", years, horizontal=True)
    target = dashboard_df[dashboard_df['입사연도'] == sel_y].copy()
    safe_update(target[['신규교육_이수','성명','입사일','부서']], "t3", {})

with tab4:
    target = dashboard_df[dashboard_df['특별교육_과목1'] != '해당없음'].copy()
    safe_update(target[['성명','부서','특별_공통_8H','특별교육_과목1','특별_1_이론_4H','특별_1_실습_4H']], "t4", {})

with tab5:
    # [확인 완료] 특수검진 대상자만 보기 (체크 해제시 사라짐)
    target = dashboard_df[dashboard_df['특수검진_대상'] == True].copy()
    if not target.empty:
        target['상태'] = target.apply(lambda r: "🔴 필요" if r['검진단계']=="배치전(미실시)" else ("🔴 초과" if pd.notnull(r['다음_특수검진일']) and (r['다음_특수검진일']-today).days<0 else "🟢 양호"), axis=1)
        safe_update(target[['성명','부서','유해인자','검진단계','최근_특수검진일','다음_특수검진일','상태']], "t5", {})
    else: st.info("대상자 없음 (검진대상 체크 확인)")
