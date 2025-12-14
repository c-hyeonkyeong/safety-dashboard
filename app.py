import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from github import Github
import io

# --- [1. 시스템 설정] ---
st.set_page_config(page_title="안전보건 대시보드 Pro", layout="wide", page_icon="🛡️")

# CSS: 사이드바 폭 조정 및 스타일
st.markdown("""
<style>
    div[data-testid="stMetricValue"] {font-size: 24px; font-weight: bold; color: #31333F;}
    div.stButton > button {width: 100%; border-radius: 6px;}
    [data-testid="stSidebar"] {min-width: 500px;}
</style>
""", unsafe_allow_html=True)

st.title("🛡️ 산업안전보건 통합 관리 시스템")
st.markdown("---")

# ==========================================
# [0. 초기 설정 및 공통 함수 (가장 먼저 정의)]
# ==========================================
SPECIAL_EDU_OPTIONS = [
    "해당없음",
    "4. 폭발성·물반응성·자기반응성·자기발열성 물질, 자연발화성 액체·고체 및 인화성 액체의 제조 또는 취급작업",
    "35. 허가 및 관리 대상 유해물질의 제조 또는 취급작업"
]

ROLES = ["안전보건관리책임자", "관리감독자", "폐기물담당자", "일반근로자"]
HEALTH_PHASES = ["배치전(미실시)", "1차검진 완료(다음:6개월)", "정기검진(다음:1년)"]

def sanitize_config_df(df):
    target_cols = ['특별교육과목1', '특별교육과목2']
    for col in target_cols:
        if col not in df.columns: df[col] = "해당없음"
    for col in target_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].apply(lambda x: x if x in SPECIAL_EDU_OPTIONS else "해당없음")
    
    if '담당관리감독자' not in df.columns: df['담당관리감독자'] = ""
    else: df['담당관리감독자'] = df['담당관리감독자'].fillna("")

    if '유해인자' not in df.columns: df['유해인자'] = "없음"
    else: df['유해인자'] = df['유해인자'].fillna("없음")
    return df

# [핵심 1] 날짜 더하기 함수 (전역)
def add_days(d, days):
    try: 
        if pd.isna(d) or str(d) == "NaT" or str(d).strip() == "": return None
        if isinstance(d, str): d = pd.to_datetime(d).date()
        if isinstance(d, datetime): d = d.date()
        return d + timedelta(days=days)
    except: return None

# [핵심 2] 직무교육 계산 함수 (전역으로 이동)
def calculate_job_training_date(row):
    last_date = row.get('최근_직무교육일')
    
    if pd.isna(last_date) or str(last_date) == 'NaT' or str(last_date).strip() == "":
        return None
    
    # 타입 보장
    if not isinstance(last_date, pd.Timestamp):
        try: last_date = pd.to_datetime(last_date)
        except: return None
            
    role = str(row.get('직책', '')).replace(" ", "").strip()
    try:
        if '책임자' in role: return last_date + timedelta(days=730)
        elif '폐기물' in role: return last_date + timedelta(days=1095)
        elif '감독자' in role: return last_date + timedelta(days=365)
        else: return None
    except: return None

# [핵심 3] D-Day 상태 표시 함수 (전역)
def get_dday_status(target_date):
    if pd.isna(target_date) or str(target_date) == 'NaT' or str(target_date).strip() == "": return "-"
    try:
        target_ts = pd.to_datetime(target_date)
        today_ts = pd.Timestamp(date.today())
        diff = (target_ts - today_ts).days
        if diff < 0: return "🔴 초과"
        elif diff < 30: return "🟡 임박"
        else: return "🟢 양호"
    except: return "-"

# 1. 근로자 명부 초기화 (df_final)
if 'df_final' not in st.session_state:
    data = {
        '성명': ['김철수', '이영희', '박신규', '최신규', '정전기', '강폐기'],
        '직책': ['안전보건관리책임자', '관리감독자', '일반근로자', '일반근로자', '일반근로자', '폐기물담당자'],
        '부서': ['일반관리팀', '일반관리팀', '용접팀', '용접팀', '전기팀', '일반관리팀'],
        '입사일': [date(2022, 1, 1), date(2023, 5, 20), date.today(), date(2020, 1, 1), date(2023, 6, 1), date(2020, 1, 1)],
        '최근_직무교육일': [date(2023, 5, 1), date(2024, 5, 20), None, None, None, date(2022, 5, 1)],
        '신규교육_이수': [False, False, False, False, False, False],
        '공통8H': [False] * 6,
        '과목1_온라인4H': [False] * 6,
        '과목1_감독자4H': [False] * 6,
        '과목2_온라인4H': [False] * 6,
        '과목2_감독자4H': [False] * 6,
        '검진단계': ['배치전(미실시)', '배치전(미실시)', '배치전(미실시)', '배치전(미실시)', '1차검진 완료(다음:6개월)', '배치전(미실시)'], 
        '최근_특수검진일': [None, None, None, None, date(2024, 12, 1), None],
        '특수검진_대상': [True, True, True, True, True, False] 
    }
    st.session_state.df_final = pd.DataFrame(data)

# 날짜/체크박스 타입 보장
date_cols = ['입사일', '최근_직무교육일', '최근_특수검진일']
for col in date_cols:
    if col in st.session_state.df_final.columns:
        st.session_state.df_final[col] = pd.to_datetime(st.session_state.df_final[col].astype(str), errors='coerce')

bool_cols = ['퇴사여부', '특수검진_대상', '신규교육_이수', '공통8H', '과목1_온라인4H', '과목1_감독자4H', '과목2_온라인4H', '과목2_감독자4H']
for col in bool_cols:
    if col not in st.session_state.df_final.columns:
        default_val = True if col == '특수검진_대상' else False
        st.session_state.df_final[col] = default_val
    else:
        st.session_state.df_final[col] = st.session_state.df_final[col].fillna(False).astype(bool)

# 2. 관리자 설정 초기화 (dept_config_final)
if 'dept_config_final' not in st.session_state:
    st.session_state.dept_config_final = pd.DataFrame({
        '정렬순서': [1, 2, 3, 4],
        '부서명': ['용접팀', '전기팀', '밀폐작업팀', '일반관리팀'],
        '특별교육과목1': ["해당없음"] * 4, '특별교육과목2': ["해당없음"] * 4,
        '유해인자': ['용접흄, 분진', '전류(감전)', '산소결핍', '없음'],
        '담당관리감독자': ['-', '-', '-', '-']
    })
st.session_state.dept_config_final = sanitize_config_df(st.session_state.dept_config_final)

# 관리감독자 명단 추출 (드롭다운용)
supervisor_list = sorted(
    st.session_state.df_final[
        st.session_state.df_final['직책'].astype(str).str.contains("관리감독자", na=False)
    ]['성명'].dropna().unique().tolist()
)
if "-" not in supervisor_list:
    supervisor_list.insert(0, "-")


# ==========================================
# [사이드바] 통합 메뉴
# ==========================================
with st.sidebar:
    st.header("⚙️ 통합 관리자 메뉴")
    
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("🔄 새로고침", type="primary"):
            st.cache_data.clear()
            st.session_state.clear()
            st.rerun()
            
    with st.expander("☁️ GitHub 토큰 설정", expanded=False):
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
            st.error("토큰 필요")
            return
        try:
            save_df = data_df.copy()
            date_cols = ['입사일', '최근_직무교육일', '최근_특수검진일', '다음_직무교육일', '다음_특수검진일']
            for col in date_cols:
                if col in save_df.columns:
                    save_df[col] = save_df[col].apply(lambda x: x.strftime('%Y-%m-%d') if not pd.isna(x) else '')

            data_content = save_df.to_csv(index=False)
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
            st.error(f"저장 실패: {e}")

    def load_all_from_github():
        repo = get_github_repo()
        if not repo: return None, None
        loaded_data, loaded_config = None, None
        try:
            contents = repo.get_contents(DATA_FILE)
            csv_string = contents.decoded_content.decode("utf-8")
            loaded_data = pd.read_csv(io.StringIO(csv_string))
            
            date_cols = ['입사일', '최근_직무교육일', '최근_특수검진일']
            for col in date_cols:
                if col in loaded_data.columns:
                    loaded_data[col] = pd.to_datetime(loaded_data[col].astype(str), errors='coerce')
            
            if '검진단계' not in loaded_data.columns: loaded_data['검진단계'] = "배치전(미실시)"
            else: loaded_data['검진단계'] = loaded_data['검진단계'].fillna("배치전(미실시)")

        except: pass
        try:
            contents = repo.get_contents(CONFIG_FILE)
            csv_string = contents.decoded_content.decode("utf-8")
            loaded_config = pd.read_csv(io.StringIO(csv_string))
            loaded_config = sanitize_config_df(loaded_config)
        except: pass
        return loaded_data, loaded_config

    with col_btn2:
        if st.button("📂 불러오기"):
            ld, lc = load_all_from_github()
            if ld is not None: 
                st.session_state.df_final = ld
                st.toast("로드 완료!", icon="✅")
            if lc is not None: st.session_state.dept_config_final = lc
            st.rerun()
            
    with col_btn3:
        if st.button("💾 저장하기"):
            if 'df_final' in st.session_state and 'dept_config_final' in st.session_state:
                save_all_to_github(st.session_state.df_final, st.session_state.dept_config_final)
            else:
                st.error("데이터 없음")

    st.divider()

    # -----------------------------------------------
    # 1. 부서 및 교육 매핑 설정
    # -----------------------------------------------
    with st.expander("🛠️ 부서 및 교육 매핑 설정", expanded=False):
        dept_file = st.file_uploader("설정 파일 (xlsx/csv)", type=['csv', 'xlsx'], key="dept_up")
        if dept_file:
            try:
                new_d = pd.read_csv(dept_file) if dept_file.name.endswith('.csv') else pd.read_excel(dept_file)
                if st.button("부서 설정 덮어쓰기"):
                    if '부서명' not in new_d.columns: st.error("부서명 컬럼 없음")
                    else:
                        new_d = new_d.rename(columns={'특별교육 1':'특별교육과목1', '특별교육 2':'특별교육과목2'})
                        new_d = sanitize_config_df(new_d)
                        cols = ['부서명', '특별교육과목1', '특별교육과목2', '유해인자', '담당관리감독자']
                        for c in cols: 
                            if c not in new_d.columns: new_d[c] = "해당없음" if "특별" in c else ""
                        final_d = pd.concat([st.session_state.dept_config_final[cols], new_d[cols]]).drop_duplicates(['부서명'], keep='last').reset_index(drop=True)
                        final_d.insert(0, '정렬순서', range(1, len(final_d)+1))
                        st.session_state.dept_config_final = final_d
                        st.rerun()
            except Exception as e: st.error(str(e))

        st.caption("담당 관리감독자는 명부에 있는 '관리감독자'만 선택 가능합니다.")
        sorted_df = st.session_state.dept_config_final.sort_values('정렬순서')
        
        edited_dept_config = st.data_editor(
            sorted_df, num_rows="dynamic", key="dept_editor_sidebar", use_container_width=True, hide_index=True,
            column_config={
                "부서명": st.column_config.TextColumn("부서명"),
                "담당관리감독자": st.column_config.SelectboxColumn("담당 관리감독자", options=supervisor_list, width="medium"),
                "특별교육과목1": st.column_config.SelectboxColumn("특별교육 1", width="medium", options=SPECIAL_EDU_OPTIONS),
                "특별교육과목2": st.column_config.SelectboxColumn("특별교육 2", width="medium", options=SPECIAL_EDU_OPTIONS),
                "유해인자": st.column_config.TextColumn("유해인자")
            }
        )
        if not sorted_df.equals(edited_dept_config):
            st.session_state.dept_config_final = edited_dept_config

    DEPT_S1 = dict(zip(st.session_state.dept_config_final['부서명'], st.session_state.dept_config_final['특별교육과목1']))
    DEPT_S2 = dict(zip(st.session_state.dept_config_final['부서명'], st.session_state.dept_config_final['특별교육과목2']))
    DEPT_FAC = dict(zip(st.session_state.dept_config_final['부서명'], st.session_state.dept_config_final['유해인자']))
    DEPT_SUP = dict(zip(st.session_state.dept_config_final['부서명'], st.session_state.dept_config_final['담당관리감독자']))
    DEPTS_LIST = list(st.session_state.dept_config_final['부서명'])

    st.divider()

    # -----------------------------------------------
    # 2. 근로자 명부 관리
    # -----------------------------------------------
    with st.expander("📝 근로자 명부 관리 (파일/수정)", expanded=True):
        with st.popover("📂 명부 파일 등록 (Excel/CSV)"):
            up_file = st.file_uploader("파일 선택", type=['csv', 'xlsx'], key="worker_up")
            if up_file:
                try:
                    new_df = pd.read_csv(up_file) if up_file.name.endswith('.csv') else pd.read_excel(up_file)
                    if st.button("명부 병합하기"):
                        if '성명' not in new_df.columns: st.error("성명 컬럼 필수")
                        else:
                            for c in st.session_state.df_final.columns:
                                if c not in new_df.columns: new_df[c] = None
                            if '특수검진_대상' in new_df.columns:
                                new_df['특수검진_대상'] = new_df['특수검진_대상'].fillna(True).astype(bool)
                            else: new_df['특수검진_대상'] = True
                            st.session_state.df_final = pd.concat([st.session_state.df_final, new_df[st.session_state.df_final.columns]], ignore_index=True)
                            st.rerun()
                except Exception as e: st.error(str(e))

        st.caption("특수검진 제외는 여기서 체크 해제")
        edited_df = st.data_editor(
            st.session_state.df_final,
            num_rows="dynamic",
            use_container_width=True,
            key="main_editor_sidebar",
            column_config={
                "퇴사여부": st.column_config.CheckboxColumn("퇴사", default=False, width="small"),
                "특수검진_대상": st.column_config.CheckboxColumn("검진대상", default=True, width="small"),
                "성명": st.column_config.TextColumn("성명", width="medium"),
                "직책": st.column_config.SelectboxColumn("직책", options=ROLES, width="medium"),
                "부서": st.column_config.SelectboxColumn("부서", options=DEPTS_LIST, width="medium"),
                "입사일": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "최근_직무교육일": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "최근_특수검진일": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "검진단계": st.column_config.SelectboxColumn(options=HEALTH_PHASES)
            }
        )
        if not st.session_state.df_final.equals(edited_df):
            st.session_state.df_final = edited_df

# ==========================================
# [메인 화면] 계산 및 대시보드
# ==========================================

# 1. 계산 로직
df = st.session_state.df_final.copy()
today = date.today()

# 이름 없는 빈 줄 제거
if '성명' in df.columns:
    df = df.dropna(subset=['성명'])
    df = df[df['성명'].astype(str).str.strip() != '']

for col in ['입사일', '최근_직무교육일', '최근_특수검진일']:
    if col in df.columns: 
        df[col] = pd.to_datetime(df[col], errors='coerce')

df['특별교육_과목1'] = df['부서'].map(DEPT_S1).fillna("설정필요")
df['특별교육_과목2'] = df['부서'].map(DEPT_S2).fillna("해당없음")
df['유해인자'] = df['부서'].map(DEPT_FAC).fillna("없음")
df['담당관리감독자'] = df['부서'].map(DEPT_SUP).fillna("-")

mask_no_factor = df['유해인자'].isin(['없음', '', '해당없음'])
df.loc[mask_no_factor, '특수검진_대상'] = False

df['입사일_dt'] = pd.to_datetime(df['입사일'].astype(str), errors='coerce')
df['입사연도'] = df['입사일_dt'].dt.year
df['법적_신규자'] = df['입사일_dt'].apply(lambda x: (pd.Timestamp(today) - x).days < 90 if pd.notnull(x) else False)

# [함수 사용] 직무교육일 계산
df['다음_직무교육일'] = df.apply(calculate_job_training_date, axis=1)

def calc_next_health(row):
    if not row.get('특수검진_대상', True): return None 
    if row['검진단계'] == "배치전(미실시)" or pd.isna(row['최근_특수검진일']): return None
    cycle = 180 if row['검진단계'] == "1차검진 완료(다음:6개월)" else 365
    return add_days(row['최근_특수검진일'], cycle)

df['다음_특수검진일'] = df.apply(calc_next_health, axis=1)

# 필터링
with st.expander("🔍 데이터 필터링 (이름/부서/직책 검색)", expanded=False):
    c1, c2, c3 = st.columns(3)
    search_name = c1.text_input("이름 검색 (엔터)")
    all_depts = sorted(df['부서'].dropna().unique())
    all_roles = sorted(df['직책'].dropna().unique())
    search_dept = c2.multiselect("부서 선택", options=all_depts)
    search_role = c3.multiselect("직책 선택", options=all_roles)

view_df = df.copy()
if search_name:
    view_df = view_df[view_df['성명'].astype(str).str.contains(search_name)]
if search_dept:
    view_df = view_df[view_df['부서'].isin(search_dept)]
if search_role:
    view_df = view_df[view_df['직책'].isin(search_role)]

active_df = view_df[view_df['퇴사여부'] == False]
this_year_hires_count = len(view_df[view_df['입사연도'] == today.year])

# 2. 대시보드
col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("👥 조회 인원(재직)", f"{len(active_df)}명")
with col2: st.metric("🌱 올해 신규 입사자", f"{this_year_hires_count}명")
with col3: st.metric("👔 책임자/감독자", f"{len(active_df[active_df['직책'].isin(['안전보건관리책임자', '관리감독자'])])}명")
with col4: st.metric("🏥 검진 대상", f"{len(active_df[active_df['특수검진_대상'] == True])}명")

st.divider()

# 3. 탭 구성
tab1, tab2, tab3, tab4, tab5 = st.tabs(["👔 책임자/감독자", "♻️ 폐기물 담당자", "🌱 신규 입사자", "⚠️ 특별교육", "🏥 특수건강검진"])

with tab1:
    st.subheader("안전보건관리책임자 (2년) / 관리감독자 (1년)")
    mask_mgr = active_df['직책'].astype(str).str.replace(" ", "").str.contains("책임자|감독자", na=False)
    target_indices = active_df[mask_mgr].index
    target = active_df.loc[target_indices].copy()
    
    if not target.empty:
        target['상태'] = target['다음_직무교육일'].apply(get_dday_status)
        
        edited_target = st.data_editor(
            target[['성명','직책','최근_직무교육일','다음_직무교육일','상태']], 
            key="mgr_editor",
            use_container_width=True, hide_index=True,
            column_config={
                "최근_직무교육일": st.column_config.DateColumn(format="YYYY-MM-DD"), 
                "다음_직무교육일": st.column_config.DateColumn(format="YYYY-MM-DD", disabled=True)
            }
        )
        
        edited_target.index = target.index
        if not target[['최근_직무교육일']].equals(edited_target[['최근_직무교육일']]):
            st.session_state.df_final.loc[target_indices, '최근_직무교육일'] = edited_target['최근_직무교육일']
            st.rerun()
    else: st.info("대상자 없음")

with tab2:
    st.subheader("폐기물 담당자 (3년)")
    mask_waste = active_df['직책'].astype(str).str.replace(" ", "").str.contains("폐기물", na=False)
    target_indices = active_df[mask_waste].index
    target = active_df.loc[target_indices].copy()
    
    if not target.empty:
        target['상태'] = target['다음_직무교육일'].apply(get_dday_status)
        
        edited_target = st.data_editor(
            target[['성명','부서','최근_직무교육일','다음_직무교육일','상태']], 
            key="waste_editor",
            use_container_width=True, hide_index=True,
            column_config={
                "최근_직무교육일": st.column_config.DateColumn(format="YYYY-MM-DD"), 
                "다음_직무교육일": st.column_config.DateColumn(format="YYYY-MM-DD", disabled=True)
            }
        )
        
        edited_target.index = target.index
        if not target[['최근_직무교육일']].equals(edited_target[['최근_직무교육일']]):
            st.session_state.df_final.loc[target_indices, '최근_직무교육일'] = edited_target['최근_직무교육일']
            st.rerun()
    else: st.info("대상자 없음")

with tab3:
    years = [today.year, today.year-1, today.year-2]
    sel_y = st.radio("입사년도 선택", years, horizontal=True)
    
    target_indices = view_df[view_df['입사연도'] == sel_y].index
    target = view_df.loc[target_indices].copy()
    
    if not target.empty:
        edited_target = st.data_editor(
            target[['신규교육_이수','퇴사여부','성명','입사일','부서','담당관리감독자']],
            key="new_edu_editor",
            hide_index=True, use_container_width=True,
            column_config={
                "신규교육_이수": st.column_config.CheckboxColumn("이수 여부", width="small"),
                "퇴사여부": st.column_config.CheckboxColumn("퇴사", disabled=True, width="small"),
                "입사일": st.column_config.DateColumn(format="YYYY-MM-DD", disabled=True),
                "성명": st.column_config.TextColumn(disabled=True),
                "부서": st.column_config.TextColumn(disabled=True),
                "담당관리감독자": st.column_config.TextColumn(disabled=True, width="medium")
            }
        )
        edited_target.index = target.index
        if not target[['신규교육_이수']].equals(edited_target[['신규교육_이수']]):
            st.session_state.df_final.loc[target_indices, '신규교육_이수'] = edited_target['신규교육_이수']
            st.rerun()
    else: st.info("대상자 없음")

with tab4:
    st.subheader("특별안전보건교육 이수 관리")
    
    target_indices = active_df[
        (active_df['특별교육_과목1'] != '해당없음') & 
        (active_df['특수검진_대상'] == True)
    ].index
    target = active_df.loc[target_indices].copy()
    
    if not target.empty:
        cols_to_show = ['성명','부서','특별교육_과목1','공통8H','과목1_온라인4H','과목1_감독자4H','특별교육_과목2','과목2_온라인4H','과목2_감독자4H']
        
        edited_target = st.data_editor(
            target[cols_to_show],
            key="special_edu_editor",
            hide_index=True, use_container_width=True,
            column_config={
                "성명": st.column_config.TextColumn(disabled=True),
                "부서": st.column_config.TextColumn(disabled=True),
                "특별교육_과목1": st.column_config.TextColumn(disabled=True),
                "특별교육_과목2": st.column_config.TextColumn(disabled=True),
                "공통8H": st.column_config.CheckboxColumn("공통 8H", width="small"),
                "과목1_온라인4H": st.column_config.CheckboxColumn("과목1-온라인", width="small"),
                "과목1_감독자4H": st.column_config.CheckboxColumn("과목1-감독자", width="small"),
                "과목2_온라인4H": st.column_config.CheckboxColumn("과목2-온라인", width="small"),
                "과목2_감독자4H": st.column_config.CheckboxColumn("과목2-감독자", width="small"),
            }
        )
        edited_target.index = target.index
        check_cols = ['공통8H','과목1_온라인4H','과목1_감독자4H','과목2_온라인4H','과목2_감독자4H']
        
        if not target[check_cols].equals(edited_target[check_cols]):
            st.session_state.df_final.loc[target_indices, check_cols] = edited_target[check_cols]
            st.rerun()
    else: st.info("특별교육 대상자가 없습니다. (검진대상 체크 여부 확인)")

with tab5:
    st.subheader("특수건강검진 현황")
    
    target_indices = active_df[active_df['특수검진_대상'] == True].index
    target = active_df.loc[target_indices].copy()
    
    if not target.empty:
        target['상태'] = target.apply(lambda r: "🔴 검진필요" if r['검진단계']=="배치전(미실시)" else get_dday_status(r['다음_특수검진일']), axis=1)
        
        edited_target = st.data_editor(
            target[['성명','부서','유해인자','검진단계','최근_특수검진일','다음_특수검진일','상태']],
            key="health_editor_fix",
            use_container_width=True,
            hide_index=True,
            column_config={
                "최근_특수검진일": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "다음_특수검진일": st.column_config.DateColumn(format="YYYY-MM-DD", disabled=True),
                "상태": st.column_config.TextColumn(disabled=True),
                "검진단계": st.column_config.SelectboxColumn(options=HEALTH_PHASES, required=True)
            }
        )
        edited_target.index = target.index
        compare_cols = ['검진단계', '최근_특수검진일']
        
        if not target[compare_cols].equals(edited_target[compare_cols]):
            st.session_state.df_final.loc[target_indices, compare_cols] = edited_target[compare_cols]
            st.rerun()
    else: 
        st.info("대상자가 없습니다. 왼쪽 사이드바 명부에서 검진대상을 체크해주세요. (유해인자가 '없음'인 경우 자동으로 제외됩니다)")
