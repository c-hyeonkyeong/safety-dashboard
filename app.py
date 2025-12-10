import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from github import Github
import io

# --- [1. 시스템 설정] ---
st.set_page_config(page_title="완성형 안전보건 대시보드", layout="wide", page_icon="🏗️")

st.markdown("""
<style>
    div[data-testid="stMetricValue"] {font-size: 20px;}
</style>
""", unsafe_allow_html=True)

st.title("🏗️ 산업안전보건 통합 관리 시스템")
st.caption("퇴사자는 체크 시 대시보드에서 제외되며, 신규 입사자는 입사일 기준으로 자동 분류됩니다.")

# ==========================================
# [GitHub 연동 설정]
# ==========================================
GITHUB_TOKEN = st.sidebar.text_input("🔑 GitHub 토큰", type="password")
REPO_NAME = st.sidebar.text_input("📂 레포지토리 (user/repo)")
FILE_PATH = "data.csv"

def get_github_repo():
    if not GITHUB_TOKEN or not REPO_NAME:
        st.sidebar.error("토큰과 레포지토리 이름을 입력해주세요.")
        return None
    try:
        g = Github(GITHUB_TOKEN)
        return g.get_repo(REPO_NAME)
    except Exception as e:
        st.sidebar.error(f"GitHub 연결 실패: {e}")
        return None

def save_to_github(df_to_save):
    repo = get_github_repo()
    if not repo: return
    
    try:
        csv_content = df_to_save.to_csv(index=False)
        try:
            contents = repo.get_contents(FILE_PATH)
            repo.update_file(FILE_PATH, f"Update data: {datetime.now()}", csv_content, contents.sha)
            st.sidebar.success("✅ 저장 완료!")
        except:
            repo.create_file(FILE_PATH, "Initial commit", csv_content)
            st.sidebar.success("✅ 새 파일 생성 완료!")
    except Exception as e:
        st.sidebar.error(f"❌ 저장 실패: {e}")

# ★ [신규 기능] 데이터 불러오기 함수
def load_from_github():
    repo = get_github_repo()
    if not repo: return None
    
    try:
        contents = repo.get_contents(FILE_PATH)
        csv_string = contents.decoded_content.decode("utf-8")
        loaded_df = pd.read_csv(io.StringIO(csv_string))
        
        # 날짜 컬럼들을 문자열 -> 날짜 객체로 변환 (중요!)
        date_cols = ['입사일', '최근_직무교육일', '최근_특수검진일']
        for col in date_cols:
            if col in loaded_df.columns:
                loaded_df[col] = pd.to_datetime(loaded_df[col], errors='coerce').dt.date
        
        st.sidebar.success("📂 불러오기 성공!")
        return loaded_df
    except Exception as e:
        st.sidebar.error(f"불러오기 실패 (파일이 없거나 오류): {e}")
        return None

# --- [2. 사용자 설정 (관리자 메뉴) - 안전장치 포함] ---
with st.expander("⚙️ [관리자 메뉴] 부서별 교육 및 유해인자 매핑 설정", expanded=False):
    if 'dept_config' not in st.session_state:
        st.session_state.dept_config = pd.DataFrame({
            '정렬순서': [1, 2, 3, 4],
            '부서명': ['용접팀', '전기팀', '밀폐작업팀', '일반관리팀'],
            '특별교육과목': ['아크용접 등 화기작업', '고압 전기 취급 작업', '밀폐공간 내부 작업', '해당없음'],
            '유해인자': ['용접흄, 분진', '전류(감전)', '산소결핍', '없음']
        })
    
    if '정렬순서' not in st.session_state.dept_config.columns:
        st.session_state.dept_config.insert(0, '정렬순서', range(1, len(st.session_state.dept_config) + 1))

    edited_dept_config = st.data_editor(
        st.session_state.dept_config, 
        num_rows="dynamic", 
        key="dept_editor", 
        use_container_width=True,
        column_config={
            "정렬순서": st.column_config.NumberColumn("순서", format="%d"),
        }
    )
    
    if '정렬순서' in edited_dept_config.columns:
        sorted_dept_config = edited_dept_config.sort_values(by='정렬순서')
    else:
        sorted_dept_config = edited_dept_config

    DEPT_SUBJECT_MAP = dict(zip(sorted_dept_config['부서명'], sorted_dept_config['특별교육과목']))
    DEPT_FACTOR_MAP = dict(zip(sorted_dept_config['부서명'], sorted_dept_config['유해인자']))
    DEPTS_LIST = list(sorted_dept_config['부서명'])

# --- [3. 메인 데이터 초기화] ---
ROLES = ["안전보건관리책임자", "관리감독자", "폐기물담당자", "일반근로자"]
HEALTH_PHASES = ["배치전(미실시)", "1차검진 완료(다음:6개월)", "정기검진(다음:1년)"]

if 'df' not in st.session_state:
    # 기본 데이터 (불러오기 실패 시 사용)
    data = {
        '성명': ['김철수', '이영희', '박신규', '최신규', '정전기', '강폐기'],
        '직책': ['안전보건관리책임자', '관리감독자', '일반근로자', '일반근로자', '일반근로자', '폐기물담당자'],
        '부서': ['일반관리팀', '일반관리팀', '용접팀', '용접팀', '전기팀', '일반관리팀'],
        '입사일': [date(2022, 1, 1), date(2023, 5, 20), date.today(), date(2020, 1, 1), date(2023, 6, 1), date(2020, 1, 1)],
        '최근_직무교육일': [date(2023, 5, 1), date(2024, 5, 20), None, None, None, date(2022, 5, 1)],
        '특별_공통8H': [False, False, False, False, True, False],
        '특별_온라인4H': [False, False, False, False, False, False],
        '특별_감독자4H': [False, False, False, False, False, False],
        '검진단계': [
            '배치전(미실시)', '배치전(미실시)', '배치전(미실시)', 
            '배치전(미실시)', '1차검진 완료(다음:6개월)', '배치전(미실시)'
        ], 
        '최근_특수검진일': [None, None, None, None, date(2024, 12, 1), None]
    }
    st.session_state.df = pd.DataFrame(data)

if '퇴사여부' not in st.session_state.df.columns:
    st.session_state.df['퇴사여부'] = False

# --- [4. 데이터 입력 및 저장/불러오기 (사이드바)] ---
with st.sidebar:
    st.header("📝 근로자 정보 관리")
    
    # ★ 저장/불러오기 버튼 영역
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📂 불러오기"):
            loaded_data = load_from_github()
            if loaded_data is not None:
                st.session_state.df = loaded_data
                st.rerun() # 데이터 갱신 후 새로고침
    with col2:
        if st.button("GitHub에 저장", type="primary"):
            save_to_github(st.session_state.df)
            
    st.divider()
    
    edited_df = st.data_editor(
        st.session_state.df,
        num_rows="dynamic",
        use_container_width=True,
        key="main_editor",
        column_config={
            "퇴사여부": st.column_config.CheckboxColumn("퇴사", default=False),
            "성명": st.column_config.TextColumn("성명", required=True),
            "직책": st.column_config.SelectboxColumn("직책", options=ROLES),
            "부서": st.column_config.SelectboxColumn("부서(자동매핑)", options=DEPTS_LIST),
            "입사일": st.column_config.DateColumn("입사일", format="YYYY-MM-DD"),
            "최근_직무교육일": st.column_config.DateColumn("최근 직무교육일"),
            "검진단계": st.column_config.SelectboxColumn("특수검진 진행상태", options=HEALTH_PHASES, required=True),
            "최근_특수검진일": st.column_config.DateColumn("최근 검진일"),
        }
    )
    df = edited_df.copy()
    
    if '퇴사여부' not in df.columns:
        df['퇴사여부'] = False

# --- [5. 핵심 로직: 자동 매핑 & 대시보드용 필터링] ---
today = date.today()

# 1. 부서 기반 자동 매핑
df['특별교육_과목'] = df['부서'].map(DEPT_SUBJECT_MAP).fillna("설정필요")
df['유해인자'] = df['부서'].map(DEPT_FACTOR_MAP).fillna("확인필요")

# 2. 날짜 및 주기 계산
def add_days(d, days):
    if pd.isna(d) or d == "": return None
    return d + timedelta(days=days)

df['입사일_dt'] = pd.to_datetime(df['입사일'], errors='coerce')
df['입사연도'] = df['입사일_dt'].dt.year

df['법적_신규자'] = df['입사일_dt'].apply(lambda x: (pd.Timestamp(today) - x).days < 90 if pd.notnull(x) else False)

df['다음_직무교육일'] = None
mask_manager = df['직책'] == '안전보건관리책임자'
df.loc[mask_manager, '다음_직무교육일'] = df[mask_manager]['최근_직무교육일'].apply(lambda x: add_days(x, 730))
mask_supervisor = df['직책'] == '관리감독자'
df.loc[mask_supervisor, '다음_직무교육일'] = df[mask_supervisor]['최근_직무교육일'].apply(lambda x: add_days(x, 365))

def calc_next_health(row):
    if row['유해인자'] in ['없음', 'None', '', None]: return None
    status = row['검진단계']
    if status == "배치전(미실시)": return None 
    if pd.isna(row['최근_특수검진일']): return None
    cycle = 180 if status == "1차검진 완료(다음:6개월)" else 365
    return row['최근_특수검진일'] + timedelta(days=cycle)

df['다음_특수검진일'] = df.apply(calc_next_health, axis=1)

dashboard_df = df[df['퇴사여부'] == False].copy()

# --- [6. 대시보드 탭 구성] ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "👔 책임자/감독자", "♻️ 폐기물 담당자", "🌱 신규 입사자 현황", "⚠️ 특별교육", "🏥 특수건강검진"
])

with tab1:
    st.subheader("안전보건관리책임자 및 관리감독자")
    target = dashboard_df[dashboard_df['직책'].isin(['안전보건관리책임자', '관리감독자'])]
    
    alert_manager = target[target['다음_직무교육일'] < today + timedelta(days=30)]
    if not alert_manager.empty: st.error(f"🚨 교육 기한 임박: {len(alert_manager)}명")
    st.dataframe(target[['성명', '직책', '최근_직무교육일', '다음_직무교육일']], use_container_width=True)

with tab2:
    st.subheader("폐기물 담당자")
    target = dashboard_df[dashboard_df['직책'] == '폐기물담당자']
    st.dataframe(target[['성명', '부서', '최근_직무교육일']], use_container_width=True)

with tab3:
    st.subheader("연도별 신규 입사자 현황")
    st.caption("최근 3개년 입사자를 조회합니다.")
    current_year = today.year
    recent_years = [current_year, current_year-1, current_year-2]
    selected_year = st.selectbox("입사 연도 선택", recent_years)
    new_hire_df = dashboard_df[dashboard_df['입사연도'] == selected_year]
    if new_hire_df.empty:
        st.info(f"{selected_year}년도 입사자가 없습니다.")
    else:
        st.dataframe(new_hire_df[['성명', '입사일', '부서', '직책']], use_container_width=True)

with tab4:
    st.subheader("특별안전보건교육 이수 현황")
    special_target = dashboard_df[dashboard_df['특별교육_과목'] != '해당없음'].copy()
    if special_target.empty:
        st.info("특별교육 대상자가 없습니다.")
    else:
        display_special = special_target[['성명', '부서', '특별교육_과목', '법적_신규자']].copy()
        display_special['공통(8H)'] = special_target.apply(
            lambda x: "✅신규갈음" if x['법적_신규자'] else ("🟢이수" if x['특별_공통8H'] else "❌미이수"), axis=1
        )
        display_special['이론(4H)'] = special_target['특별_온라인4H'].apply(lambda x: "🟢이수" if x else "❌미이수")
        display_special['실습(4H)'] = special_target['특별_감독자4H'].apply(lambda x: "🟢이수" if x else "❌미이수")
        def check_final(row):
            common_ok = row['법적_신규자'] or row['특별_공통8H']
            subject_ok = row['특별_온라인4H'] and row['특별_감독자4H']
            return "🎉완료" if common_ok and subject_ok else "⚠️교육필요"
        display_special['최종상태'] = special_target.apply(check_final, axis=1)
        st.dataframe(display_special, use_container_width=True)

with tab5:
    st.subheader("특수건강검진 대상자")
    health_target = dashboard_df[(dashboard_df['유해인자'].notna()) & (dashboard_df['유해인자'] != '없음')].copy()
    if health_target.empty:
        st.info("특수건강검진 대상자가 없습니다.")
    else:
        def get_health_status(row):
            if row['검진단계'] == "배치전(미실시)": return "🚨 배치 전 검진 필요"
            if pd.isna(row['다음_특수검진일']): return "-"
            days_left = (row['다음_특수검진일'] - today).days
            if days_left < 0: return "❌ 기한 초과"
            if days_left < 30: return "⚠️ 기한 임박"
            return f"✅ 양호 ({days_left}일)"
        health_target['상태'] = health_target.apply(get_health_status, axis=1)
        st.dataframe(health_target[['성명', '부서', '유해인자', '검진단계', '최근_특수검진일', '다음_특수검진일', '상태']], use_container_width=True)
