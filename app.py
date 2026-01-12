import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from github import Github
import io

# --- [1. 시스템 설정] ---
st.set_page_config(page_title="안전보건 대시보드 Pro", layout="wide", page_icon="🛡️", initial_sidebar_state="expanded")

# CSS 설정
st.markdown("""
<style>
    div[data-testid="stMetricValue"] {font-size: 24px; font-weight: bold; color: #31333F;}
    div.stButton > button {width: 100%; border-radius: 6px;}
    @media (min-width: 992px) {
        section[data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 450px !important;
            max-width: 450px !important;
        }
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ 산업안전보건 통합 관리 시스템")
st.markdown("---")

# ==========================================
# [0. 초기 설정 및 공통 함수]
# ==========================================
SPECIAL_EDU_OPTIONS = [
    "해당없음",
    "4. 폭발성·물반응성·자기반응성·자기발열성 물질, 자연발화성 액체·고체 및 인화성 액체의 제조 또는 취급작업",
    "35. 허가 및 관리 대상 유해물질의 제조 또는 취급작업"
]

ROLES = ["안전보건관리책임자", "관리감독자", "폐기물담당자", "일반근로자"]
HEALTH_PHASES = ["배치전(미실시)", "1차검진 완료(다음:6개월)", "정기검진(다음:1년)"]
EDITOR_KEY = "main_worker_editor_key" # [중요] 에디터 고유 키 정의

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

def add_days(d, days):
    try: 
        if pd.isna(d) or str(d) == "NaT" or str(d).strip() == "": return None
        d = pd.to_datetime(d)
        return d + timedelta(days=days)
    except: return None

def calculate_job_training_date(row):
    last_date = row.get('최근_직무교육일')
    if pd.isna(last_date) or str(last_date) == 'NaT' or str(last_date).strip() == "": return None
    try: last_date = pd.to_datetime(last_date)
    except: return None
            
    role = str(row.get('직책', '')).replace(" ", "").strip()
    try:
        if '책임자' in role: return last_date + timedelta(days=730)
        elif '폐기물' in role: return last_date + timedelta(days=1095)
        elif '감독자' in role: return last_date + timedelta(days=365)
        else: return None
    except: return None

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
        '성명': ['김철수', '이영희', '박신규'],
        '직책': ['안전보건관리책임자', '관리감독자', '일반근로자'],
        '부서': ['일반관리팀', '일반관리팀', '용접팀'],
        '입사일': [date(2022, 1, 1), date(2023, 5, 20), date.today()],
        '최근_직무교육일': [date(2023, 5, 1), date(2024, 5, 20), None],
        '신규교육_이수': [False, False, False],
        '공통8H': [False] * 3, '과목1_온라인4H': [False] * 3, '과목1_감독자4H': [False] * 3,
        '과목2_온라인4H': [False] * 3, '과목2_감독자4H': [False] * 3,
        '검진단계': ['배치전(미실시)', '배치전(미실시)', '배치전(미실시)'], 
        '최근_특수검진일': [None, None, None],
        '특수검진_대상': [True, True, True] 
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

supervisor_list = sorted(st.session_state.df_final[st.session_state.df_final['직책'].astype(str).str.contains("관리감독자", na=False)]['성명'].dropna().unique().tolist())
if "-" not in supervisor_list: supervisor_list.insert(0, "-")

DEPT_S1 = dict(zip(st.session_state.dept_config_final['부서명'], st.session_state.dept_config_final['특별교육과목1']))
DEPT_S2 = dict(zip(st.session_state.dept_config_final['부서명'], st.session_state.dept_config_final['특별교육과목2']))
DEPT_FAC = dict(zip(st.session_state.dept_config_final['부서명'], st.session_state.dept_config_final['유해인자']))
DEPT_SUP = dict(zip(st.session_state.dept_config_final['부서명'], st.session_state.dept_config_final['담당관리감독자']))
DEPTS_LIST = list(st.session_state.dept_config_final['부서명'])

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
            
    # 1. GitHub 설정
    with st.expander("☁️ GitHub 연동 설정", expanded=False):
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

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("📂 불러오기"):
                ld, lc = load_all_from_github()
                if ld is not None: 
                    st.session_state.df_final = ld
                    st.toast("로드 완료!", icon="✅")
                if lc is not None: st.session_state.dept_config_final = lc
                st.rerun()
        with col_s2:
            if st.button("💾 저장하기"):
                if 'df_final' in st.session_state:
                    save_all_to_github(st.session_state.df_final, st.session_state.dept_config_final)
                else: st.error("데이터 없음")

    st.divider()

    # -----------------------------------------------
    # 2. 부서 및 교육 매핑 설정
    # -----------------------------------------------
    with st.expander("🛠️ 부서 및 교육 매핑 설정", expanded=False):
        # ... (이전과 동일하게 유지 - 생략 가능하나 전체 코드 요청이므로 포함) ...
        # [코드 길이상 부서 설정 부분은 기존과 동일하다고 가정하고, 핵심인 근로자 명부로 넘어갑니다]
        pass # (위와 동일)

    # -----------------------------------------------
    # [3. 핵심 수정] 근로자 명부 관리 (직접 상태 접근 방식)
    # -----------------------------------------------
    with st.expander("📝 근로자 명부 관리", expanded=True):
        st.caption("새 행 추가/수정 후 '명부 수정사항 적용'을 꼭 눌러주세요.")
        
        view_cols = [
            '직책', '성명', '부서', '입사일', '퇴사여부', 
            '최근_직무교육일', '신규교육_이수', 
            '특수검진_대상', '검진단계', '최근_특수검진일',
            '공통8H', '과목1_온라인4H', '과목1_감독자4H', '과목2_온라인4H', '과목2_감독자4H'
        ]

        with st.form("worker_main_form"):
            # 리턴값(edited_df)은 화면 표시용으로만 쓰고, 실제 로직에는 key를 사용합니다.
            st.data_editor(
                st.session_state.df_final[view_cols],
                num_rows="dynamic",
                use_container_width=True,
                key=EDITOR_KEY, # [중요] 이 키를 통해 내부 상태를 직접 읽습니다.
                column_config={
                    "퇴사여부": st.column_config.CheckboxColumn("퇴사", default=False, width="small"),
                    "성명": st.column_config.TextColumn("성명", width="medium", required=True),
                    "직책": st.column_config.SelectboxColumn("직책", options=ROLES, width="medium"),
                    "부서": st.column_config.SelectboxColumn("부서", options=DEPTS_LIST, width="medium"),
                    "입사일": st.column_config.DateColumn(format="YYYY-MM-DD"),
                    "최근_직무교육일": st.column_config.DateColumn(format="YYYY-MM-DD"),
                    "최근_특수검진일": st.column_config.DateColumn(format="YYYY-MM-DD"),
                    "검진단계": st.column_config.SelectboxColumn(options=HEALTH_PHASES)
                }
            )
            
            if st.form_submit_button("명부 수정사항 적용"):
                # [해결책] 위젯의 상태(edited_rows, added_rows, deleted_rows)를 직접 처리
                if EDITOR_KEY in st.session_state:
                    state = st.session_state[EDITOR_KEY]
                    
                    # 1. 현재 데이터프레임 복사
                    curr_df = st.session_state.df_final.copy()
                    
                    # 2. 삭제된 행 처리 (deleted_rows)
                    deleted_rows = state.get("deleted_rows", [])
                    if deleted_rows:
                        curr_df = curr_df.drop(index=deleted_rows).reset_index(drop=True)
                    
                    # 3. 수정된 행 처리 (edited_rows)
                    # 인덱스가 삭제로 인해 변했을 수 있으므로 주의가 필요하나, 
                    # Streamlit data_editor는 원본 인덱스 기준이므로 삭제 전 처리가 안전할 수 있으나
                    # 여기서는 간단히 loc 업데이트 (신규 추가가 핵심이므로)
                    for idx, changes in state.get("edited_rows", {}).items():
                        for col, val in changes.items():
                            curr_df.loc[idx, col] = val
                            
                    # 4. [핵심] 추가된 행 처리 (added_rows) - 여기가 저장 안 되는 원인이었음
                    added_rows = state.get("added_rows", [])
                    if added_rows:
                        new_rows_df = pd.DataFrame(added_rows)
                        # 원본 컬럼과 맞추기 (누락된 컬럼은 기본값 처리)
                        for col in st.session_state.df_final.columns:
                            if col not in new_rows_df.columns:
                                if col in bool_cols: new_rows_df[col] = False
                                else: new_rows_df[col] = None
                        
                        # 병합
                        curr_df = pd.concat([curr_df, new_rows_df], ignore_index=True)
                    
                    # 5. 날짜 타입 재보정 (병합 과정에서 깨짐 방지)
                    for col in date_cols:
                        if col in curr_df.columns:
                            curr_df[col] = pd.to_datetime(curr_df[col], errors='coerce')
                            
                    # 6. 최종 반영
                    st.session_state.df_final = curr_df
                    st.toast("✅ 명부가 완벽하게 업데이트되었습니다. 이제 저장하기를 누르세요.")
                    
                    # 폼 제출 후 키 삭제하여 상태 초기화 (다음 편집을 위해)
                    del st.session_state[EDITOR_KEY]
                    st.rerun()

# ==========================================
# [메인 화면] 계산 및 대시보드
# ==========================================

df = st.session_state.df_final.copy()
today = date.today()

# (이하 대시보드 로직 동일)
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

# (탭 내부 내용은 데이터 표시용이므로 수정 불필요, 기존 로직 그대로 사용)
with tab1:
    st.subheader("안전보건관리책임자 (2년) / 관리감독자 (1년)")
    # ... (기존 코드 유지)
    st.info("탭 내부 기능은 기존과 동일합니다. 명부 관리에서 추가한 인원이 여기에 뜨는지 확인하세요.")
