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
# [설정] 공통 변수 및 함수
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
    if '유해인자' not in df.columns: df['유해인자'] = "없음"
    else: df['유해인자'] = df['유해인자'].fillna("없음")
    return df

# ==========================================
# [사이드바] 모든 입력 및 설정 기능 통합
# ==========================================
with st.sidebar:
    st.header("⚙️ 통합 관리자 메뉴")
    
    # 1. GitHub 및 서버 설정
    with st.expander("☁️ 서버/저장소 연결", expanded=False):
        if st.button("🔄 강제 새로고침 (오류 해결용)", type="primary"):
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
            st.error("토큰 확인 필요")
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
            st.error(f"저장 실패: {e}")

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

    st.divider()

    # 2. 관리자 설정 (부서 매핑)
    if 'dept_config_final' not in st.session_state:
        st.session_state.dept_config_final = pd.DataFrame({
            '정렬순서': [1, 2, 3, 4],
            '부서명': ['용접팀', '전기팀', '밀폐작업팀', '일반관리팀'],
            '특별교육과목1': ["해당없음"] * 4, '특별교육과목2': ["해당없음"] * 4,
            '유해인자': ['용접흄, 분진', '전류(감전)', '산소결핍', '없음']
        })
    st.session_state.dept_config_final = sanitize_config_df(st.session_state.dept_config_final)

    with st.expander("🛠️ 부서 및 교육 매핑 설정"):
        dept_file = st.file_uploader("설정 파일 (xlsx/csv)", type=['csv', 'xlsx'], key="dept_up")
        if dept_file:
            try:
                new_d = pd.read_csv(dept_file) if dept_file.name.endswith('.csv') else pd.read_excel(dept_file)
                if st.button("부서 설정 덮어쓰기"):
                    if '부서명' not in new_d.columns: st.error("부서명 컬럼 없음")
                    else:
                        new_d = new_d.rename(columns={'특별교육 1':'특별교육과목1', '특별교육 2':'특별교육과목2'})
                        new_d = sanitize_config_df(new_d)
                        cols = ['부서명', '특별교육과목1', '특별교육과목2', '유해인자']
                        for c in cols: 
                            if c not in new_d.columns: new_d[c] = "해당없음" if "특별" in c else "없음"
                        final_d = pd.concat([st.session_state.dept_config_final[cols], new_d[cols]]).drop_duplicates(['부서명'], keep='last').reset_index(drop=True)
                        final_d.insert(0, '정렬순서', range(1, len(final_d)+1))
                        st.session_state.dept_config_final = final_d
                        st.rerun()
            except Exception as e: st.error(str(e))

        st.caption("아래 표를 직접 수정하세요.")
        sorted_df = st.session_state.dept_config_final.sort_values('정렬순서')
        edited_dept_config = st.data_editor(
            sorted_df, num_rows="dynamic", key="dept_editor_sidebar", use_container_width=True, hide_index=True,
            column_config={
                "부서명": st.column_config.TextColumn("부서명"),
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
    DEPTS_LIST = list(st.session_state.dept_config_final['부서명'])

    st.divider()

    # 3. 데이터 저장/로드 및 명부 수정
    st.subheader("📝 근로자 명부 관리")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📂 불러오기"):
            ld, lc = load_all_from_github()
            if ld is not None: st.session_state.df_final = ld
            if lc is not None: st.session_state.dept_config_final = lc
            st.rerun()
    with c2:
        if st.button("💾 저장하기", type="primary"):
            save_all_to_github(st.session_state.df_final, st.session_state.dept_config_final)

    # 데이터 초기화
    if 'df_final' not in st.session_state:
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
        st.session_state.df_final = pd.DataFrame(data)

    if '특수검진_대상' not in st.session_state.df_final.columns:
        st.session_state.df_final['특수검진_대상'] = True
    required_columns = ['퇴사여부', '신규교육_이수', '특별_공통_8H', '특별_1_이론_4H', '특별_1_실습_4H', '특별_2_이론_4H', '특별_2_실습_4H']
    for col in required_columns:
        if col not in st.session_state.df_final.columns:
            st.session_state.df_final[col] = False

    with st.expander("📂 명부 파일 등록"):
        up_file = st.file_uploader("명부 파일 (xlsx/csv)", type=['csv', 'xlsx'], key="worker_up")
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

    st.markdown("##### 👥 명부 직접 수정")
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
            "최근_직무교육일": st.column_config.DateColumn(),
            "검진단계": None, "최근_특수검진일": None
        }
    )
    if not st.session_state.df_final.equals(edited_df):
        st.session_state.df_final = edited_df


# ==========================================
# [메인 화면] 계산 및 대시보드 출력
# ==========================================

# 1. 계산 로직
df = st.session_state.df_final.copy()
today = date.today()

for col in ['입사일', '최근_직무교육일', '최근_특수검진일']:
    if col in df.columns: df[col] = pd.to_datetime(df[col].astype(str), errors='coerce').dt.date

df['특별교육_과목1'] = df['부서'].map(DEPT_S1).fillna("설정필요")
df['특별교육_과목2'] = df['부서'].map(DEPT_S2).fillna("해당없음")
df['유해인자'] = df['부서'].map(DEPT_FAC).fillna("확인필요")

def add_days(d, days):
    try: return d + timedelta(days=days)
    except: return None

df['입사일_dt'] = pd.to_datetime(df['입사일'].astype(str), errors='coerce')
df['입사연도'] = df['입사일_dt'].dt.year
df['법적_신규자'] = df['입사일_dt'].apply(lambda x: (pd.Timestamp(today) - x).days < 90 if pd.notnull(x) else False)

df['다음_직무교육일'] = None
df.loc[df['직책']=='안전보건관리책임자', '다음_직무교육일'] = df['최근_직무교육일'].apply(lambda x: add_days(x, 730))
df.loc[df['직책']=='관리감독자', '다음_직무교육일'] = df['최근_직무교육일'].apply(lambda x: add_days(x, 365))
mask_waste = df['직책'].astype(str).str.strip() == '폐기물담당자'
df.loc[mask_waste, '다음_직무교육일'] = df[mask_waste]['최근_직무교육일'].apply(lambda x: add_days(x, 1095))

def calc_next_health(row):
    if not row.get('특수검진_대상', True): return None 
    if row['검진단계'] == "배치전(미실시)" or pd.isna(row['최근_특수검진일']): return None
    cycle = 180 if row['검진단계'] == "1차검진 완료(다음:6개월)" else 365
    return add_days(row['최근_특수검진일'], cycle)

df['다음_특수검진일'] = df.apply(calc_next_health, axis=1)
dashboard_df = df[df['퇴사여부'] == False]

# 2. 대시보드 출력
col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("👥 총 관리 인원", f"{len(dashboard_df)}명")
with col2: st.metric("🌱 신규 입사자", f"{len(dashboard_df[dashboard_df['법적_신규자']])}명")
with col3: st.metric("👔 책임자/감독자", f"{len(dashboard_df[dashboard_df['직책'].isin(['안전보건관리책임자', '관리감독자'])])}명")
with col4: st.metric("🏥 검진 대상", f"{len(dashboard_df[dashboard_df['특수검진_대상'] == True])}명")

st.divider()

# 3. 탭 구성
tab1, tab2, tab3, tab4, tab5 = st.tabs(["👔 책임자/감독자", "♻️ 폐기물 담당자", "🌱 신규 입사자", "⚠️ 특별교육", "🏥 특수건강검진"])

def safe_update_simple(target_df, key, cols):
    st.data_editor(
        target_df.reset_index(drop=True), 
        key=key, hide_index=True, use_container_width=True, 
        column_config=cols
    )

with tab1:
    target = dashboard_df[dashboard_df['직책'].isin(['안전보건관리책임자', '관리감독자'])].copy()
    if not target.empty:
        target['상태'] = target.apply(lambda r: "🔴 초과" if pd.isna(r['다음_직무교육일']) or (r['다음_직무교육일']-today).days<0 else "🟢 양호", axis=1)
        safe_update_simple(target[['성명','직책','최근_직무교육일','다음_직무교육일','상태']], "t1", {"다음_직무교육일": st.column_config.DateColumn()})
    else: st.info("대상자 없음")

with tab2:
    target = dashboard_df[dashboard_df['직책'].astype(str).str.strip() == '폐기물담당자'].copy()
    if not target.empty:
        target['상태'] = target.apply(lambda r: "🔴 필요" if pd.isna(r['최근_직무교육일']) else ("🔴 초과" if (r['다음_직무교육일']-today).days<0 else "🟢 양호"), axis=1)
        safe_update_simple(target[['성명','부서','최근_직무교육일','다음_직무교육일','상태']], "t2", {"다음_직무교육일": st.column_config.DateColumn()})
    else: st.info("대상자 없음")

with tab3:
    years = [today.year, today.year-1, today.year-2]
    sel_y = st.radio("입사년도 선택", years, horizontal=True)
    target = dashboard_df[dashboard_df['입사연도'] == sel_y].copy()
    safe_update_simple(target[['신규교육_이수','성명','입사일','부서']], "t3", {})

with tab4:
    target = dashboard_df[dashboard_df['특별교육_과목1'] != '해당없음'].copy()
    safe_update_simple(target[['성명','부서','특별_공통_8H','특별교육_과목1','특별_1_이론_4H','특별_1_실습_4H']], "t4", {})

# [중요] 특수건강검진 탭: 튕김 현상 방지 로직 적용
with tab5:
    st.subheader("특수건강검진 현황")
    
    # 체크된 사람 필터링 (인덱스 유지)
    target_indices = dashboard_df[dashboard_df['특수검진_대상'] == True].index
    target = dashboard_df.loc[target_indices].copy()
    
    if not target.empty:
        target['상태'] = target.apply(lambda r: "🔴 검진필요" if r['검진단계']=="배치전(미실시)" else ("🔴 초과" if pd.notnull(r['다음_특수검진일']) and (r['다음_특수검진일']-today).days<0 else "🟢 양호"), axis=1)
        
        # 데이터 에디터 출력
        edited_target = st.data_editor(
            target[['성명','부서','유해인자','검진단계','최근_특수검진일','다음_특수검진일','상태']],
            key="health_editor_fix",
            use_container_width=True,
            hide_index=True,
            column_config={
                "최근_특수검진일": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "다음_특수검진일": st.column_config.DateColumn(disabled=True),
                "상태": st.column_config.TextColumn(disabled=True),
                "검진단계": st.column_config.SelectboxColumn(options=HEALTH_PHASES, required=True)
            }
        )
        
        # [핵심] 변경 감지 시에만 저장 (강제 리런 제거로 입력 부드럽게)
        # 인덱스 재정렬
        edited_target.index = target.index
        compare_cols = ['검진단계', '최근_특수검진일']
        
        if not target[compare_cols].equals(edited_target[compare_cols]):
            st.session_state.df_final.loc[target_indices, compare_cols] = edited_target[compare_cols]
            # 여기서는 st.rerun()을 쓰지 않아도 Streamlit이 자연스럽게 다음 루프에서 반영합니다.
            # 만약 즉각적인 '다음예정일' 계산 갱신이 필요하면 사용자가 엔터를 치거나 다른 곳을 클릭할 때 반영됩니다.
    else: 
        st.info("대상자가 없습니다. 왼쪽 사이드바 명부에서 검진대상을 체크해주세요.")
