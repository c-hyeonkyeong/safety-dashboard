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
    .st-emotion-cache-16idsys p {font-size: 1rem;}
    div.stButton > button {
        border-radius: 6px;
        height: 32px;
        padding-top: 0px;
        padding-bottom: 0px;
        width: 100%;
    }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ 산업안전보건 통합 관리 시스템")
st.markdown("---")

# ==========================================
# [전역 설정: 특별교육 옵션]
# ==========================================
SPECIAL_EDU_OPTIONS = [
    "해당없음",
    "아크용접 등 화기작업", 
    "고압 전기 취급 작업", 
    "밀폐공간 내부 작업", 
    "그라인더 작업",
    "4. 폭발성·물반응성·자기반응성·자기발열성 물질, 자연발화성 액체·고체 및 인화성 액체의 제조 또는 취급작업",
    "35. 허가 및 관리 대상 유해물질의 제조 또는 취급작업"
]

def sanitize_config_df(df):
    """부서 설정 데이터의 유효성을 검사하고 정리하는 함수"""
    target_cols = ['특별교육과목1', '특별교육과목2']
    # 없는 컬럼 생성
    for col in target_cols:
        if col not in df.columns:
            df[col] = "해당없음"
            
    for col in target_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            # 옵션에 없는 값은 '해당없음'으로 강제 치환
            df[col] = df[col].apply(lambda x: x if x in SPECIAL_EDU_OPTIONS else "해당없음")
            
    if '유해인자' not in df.columns:
        df['유해인자'] = "없음"
    else:
        df['유해인자'] = df['유해인자'].fillna("없음")
        
    return df

# ==========================================
# [GitHub 연동 설정]
# ==========================================
with st.sidebar:
    st.header("⚙️ 시스템 설정")
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
        date_cols = ['입사일', '최근_직무교육일', '최근_특수검진일']
        for col in date_cols:
            if col in loaded_data.columns:
                loaded_data[col] = pd.to_datetime(loaded_data[col], errors='coerce').dt.date
    except: pass
    try:
        contents = repo.get_contents(CONFIG_FILE)
        csv_string = contents.decoded_content.decode("utf-8")
        loaded_config = pd.read_csv(io.StringIO(csv_string))
        loaded_config = sanitize_config_df(loaded_config)
    except: pass
    return loaded_data, loaded_config

# --- [2. 사용자 설정 (관리자 메뉴)] ---
if 'dept_config' not in st.session_state:
    st.session_state.dept_config = pd.DataFrame({
        '정렬순서': [1, 2, 3, 4],
        '부서명': ['용접팀', '전기팀', '밀폐작업팀', '일반관리팀'],
        '특별교육과목1': ['아크용접 등 화기작업', '고압 전기 취급 작업', '밀폐공간 내부 작업', '해당없음'],
        '특별교육과목2': ['그라인더 작업', '해당없음', '해당없음', '해당없음'],
        '유해인자': ['용접흄, 분진', '전류(감전)', '산소결핍', '없음']
    })
    st.session_state.dept_config = sanitize_config_df(st.session_state.dept_config)

# 컬럼 보장
for col in ['정렬순서', '부서명', '특별교육과목1', '특별교육과목2', '유해인자']:
    if col not in st.session_state.dept_config.columns:
        if col == '정렬순서':
             st.session_state.dept_config.insert(0, '정렬순서', range(1, len(st.session_state.dept_config) + 1))
        else:
            st.session_state.dept_config[col] = '해당없음'

with st.expander("🛠️ [관리자 설정] 부서 순서 및 교육 매핑", expanded=False):
    
    # --- [추가 기능] 부서 일괄 등록 ---
    with st.popover("📂 부서 설정 일괄 등록 (Excel/CSV)"):
        st.markdown("##### 부서 설정 파일 업로드")
        st.caption("필수 컬럼: **부서명** (나머지는 자동 채움)")
        dept_file = st.file_uploader("파일 선택", type=['csv', 'xlsx'], key="dept_uploader")
        
        if dept_file:
            try:
                if dept_file.name.endswith('.csv'):
                    df_dept_new = pd.read_csv(dept_file)
                else:
                    df_dept_new = pd.read_excel(dept_file)
                
                st.dataframe(df_dept_new.head(), height=100)
                
                if st.button("부서 등록 실행", type="primary"):
                    if '부서명' not in df_dept_new.columns:
                        st.error("필수 컬럼 '부서명'이 없습니다.")
                    else:
                        # 1. 데이터 정제 (옵션에 없는 값 처리)
                        df_dept_new = sanitize_config_df(df_dept_new)
                        
                        # 2. 기존 데이터와 병합 (부서명 기준 중복 제거 - 덮어쓰기)
                        current_df = st.session_state.dept_config
                        
                        # 필요한 컬럼만 추출
                        cols = ['부서명', '특별교육과목1', '특별교육과목2', '유해인자']
                        df_merged = pd.concat([current_df[cols], df_dept_new[cols]], ignore_index=True)
                        
                        # 중복된 부서명 제거 (나중에 들어온 것이 남음 = 업데이트 효과)
                        df_merged = df_merged.drop_duplicates(subset=['부서명'], keep='last')
                        
                        # 3. 정렬 순서 재부여
                        df_merged.reset_index(drop=True, inplace=True)
                        df_merged.insert(0, '정렬순서', range(1, len(df_merged) + 1))
                        
                        st.session_state.dept_config = df_merged
                        st.success(f"부서 {len(df_dept_new)}개 처리 완료!")
                        st.rerun()
            except Exception as e:
                st.error(f"오류: {e}")

    st.divider()
    st.caption("부서 순서를 변경하고, 각 부서에 해당하는 특별교육 및 유해인자를 설정하세요.")

    # 1. 순서 변경 UI
    df_config = st.session_state.dept_config.sort_values('정렬순서')
    with st.container(border=True):
        for idx, row in df_config.iterrows():
            c1, c2, c3 = st.columns([8, 1, 1], gap="small", vertical_alignment="center")
            with c1: st.markdown(f"**{row['정렬순서']}. {row['부서명']}**")
            current_order = row['정렬순서']
            with c2:
                if current_order > 1:
                    if st.button("⬆️", key=f"up_{idx}"):
                        prev_row = df_config[df_config['정렬순서'] == current_order - 1].index[0]
                        st.session_state.dept_config.at[idx, '정렬순서'] -= 1
                        st.session_state.dept_config.at[prev_row, '정렬순서'] += 1
                        st.rerun()
            with c3:
                if current_order < len(df_config):
                    if st.button("⬇️", key=f"down_{idx}"):
                        next_row = df_config[df_config['정렬순서'] == current_order + 1].index[0]
                        st.session_state.dept_config.at[idx, '정렬순서'] += 1
                        st.session_state.dept_config.at[next_row, '정렬순서'] -= 1
                        st.rerun()
            st.markdown('<hr style="margin: 5px 0; border-top: 1px solid #e0e0e0;">', unsafe_allow_html=True)

    st.markdown("#### 📝 매핑 상세 설정")
    sorted_df = sanitize_config_df(st.session_state.dept_config.sort_values('정렬순서'))
    edited_dept_config = st.data_editor(
        sorted_df, num_rows="dynamic", key="dept_editor", use_container_width=True, hide_index=True,
        column_config={
            "정렬순서": None,
            "부서명": st.column_config.TextColumn("부서명", required=True),
            "특별교육과목1": st.column_config.SelectboxColumn("특별교육 1", width="large", options=SPECIAL_EDU_OPTIONS, required=True),
            "특별교육과목2": st.column_config.SelectboxColumn("특별교육 2", width="large", options=SPECIAL_EDU_OPTIONS, required=True),
            "유해인자": st.column_config.TextColumn("유해인자", width="medium"),
        }
    )
    if not sorted_df.equals(edited_dept_config):
        st.session_state.dept_config = edited_dept_config

    DEPT_SUB1_MAP = dict(zip(st.session_state.dept_config['부서명'], st.session_state.dept_config['특별교육과목1']))
    DEPT_SUB2_MAP = dict(zip(st.session_state.dept_config['부서명'], st.session_state.dept_config['특별교육과목2']))
    DEPT_FACTOR_MAP = dict(zip(st.session_state.dept_config['부서명'], st.session_state.dept_config['유해인자']))
    DEPTS_LIST = list(st.session_state.dept_config['부서명'])

# --- [3. 메인 데이터 초기화] ---
ROLES = ["안전보건관리책임자", "관리감독자", "폐기물담당자", "일반근로자"]
HEALTH_PHASES = ["배치전(미실시)", "1차검진 완료(다음:6개월)", "정기검진(다음:1년)"]

if 'df' not in st.session_state:
    data = {
        '성명': ['김철수', '이영희', '박신규', '최신규', '정전기', '강폐기'],
        '직책': ['안전보건관리책임자', '관리감독자', '일반근로자', '일반근로자', '일반근로자', '폐기물담당자'],
        '부서': ['일반관리팀', '일반관리팀', '용접팀', '용접팀', '전기팀', '일반관리팀'],
        '입사일': [date(2022, 1, 1), date(2023, 5, 20), date.today(), date(2020, 1, 1), date(2023, 6, 1), date(2020, 1, 1)],
        '최근_직무교육일': [date(2023, 5, 1), date(2024, 5, 20), None, None, None, date(2022, 5, 1)],
        '신규교육_이수': [False, False, False, False, False, False],
        '특별_공통_8H': [False, False, False, False, True, False],
        '특별_1_이론_4H': [False, False, False, False, True, False],
        '특별_1_실습_4H': [False, False, False, False, True, False],
        '특별_2_이론_4H': [False, False, False, False, False, False],
        '특별_2_실습_4H': [False, False, False, False, False, False],
        '검진단계': ['배치전(미실시)', '배치전(미실시)', '배치전(미실시)', '배치전(미실시)', '1차검진 완료(다음:6개월)', '배치전(미실시)'], 
        '최근_특수검진일': [None, None, None, None, date(2024, 12, 1), None]
    }
    st.session_state.df = pd.DataFrame(data)

# 필수 컬럼 보장
required_columns = ['퇴사여부', '신규교육_이수', '특별_공통_8H', '특별_1_이론_4H', '특별_1_실습_4H', '특별_2_이론_4H', '특별_2_실습_4H']
for col in required_columns:
    if col not in st.session_state.df.columns:
        st.session_state.df[col] = False

# --- [4. 메인 대시보드 로직] ---
df = st.session_state.df.copy()
today = date.today()

# 매핑 적용
df['특별교육_과목1'] = df['부서'].map(DEPT_SUB1_MAP).fillna("설정필요")
df['특별교육_과목2'] = df['부서'].map(DEPT_SUB2_MAP).fillna("해당없음")
df['유해인자'] = df['부서'].map(DEPT_FACTOR_MAP).fillna("확인필요")

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
mask_waste = df['직책'] == '폐기물담당자'
df.loc[mask_waste, '다음_직무교육일'] = df[mask_waste]['최근_직무교육일'].apply(lambda x: add_days(x, 1095))

def calc_next_health(row):
    if row['유해인자'] in ['없음', 'None', '', None]: return None
    status = row['검진단계']
    if status == "배치전(미실시)": return None 
    if pd.isna(row['최근_특수검진일']): return None
    cycle = 180 if status == "1차검진 완료(다음:6개월)" else 365
    return row['최근_특수검진일'] + timedelta(days=cycle)

df['다음_특수검진일'] = df.apply(calc_next_health, axis=1)
dashboard_df = df[df['퇴사여부'] == False]

col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("👥 총 관리 인원", f"{len(dashboard_df)}명")
with col2: st.metric("🌱 신규 입사자", f"{len(dashboard_df[dashboard_df['법적_신규자']])}명")
with col3: st.metric("👔 책임자/감독자", f"{len(dashboard_df[dashboard_df['직책'].isin(['안전보건관리책임자', '관리감독자'])])}명")
with col4: st.metric("🏥 검진 대상", f"{len(dashboard_df[(dashboard_df['유해인자'].notna()) & (dashboard_df['유해인자'] != '없음')])}명")

st.markdown("---")

# --- [5. 데이터 입력 및 저장 (사이드바)] ---
with st.sidebar:
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📂 불러오기", use_container_width=True):
            ld, lc = load_all_from_github()
            if ld is not None: st.session_state.df = ld
            if lc is not None: st.session_state.dept_config = lc
            st.rerun()
    with c2:
        if st.button("💾 저장하기", type="primary", use_container_width=True):
            save_all_to_github(st.session_state.df, st.session_state.dept_config)
    st.divider()

    # --- [근로자 명부 일괄 등록] ---
    with st.expander("📂 근로자 명부 일괄 등록", expanded=False):
        uploaded_file = st.file_uploader("파일 업로드 (xlsx/csv)", type=['csv', 'xlsx'])
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_new = pd.read_csv(uploaded_file)
                else:
                    df_new = pd.read_excel(uploaded_file)
                
                st.caption(f"총 {len(df_new)}행 발견. 첫 5줄 미리보기:")
                st.dataframe(df_new.head(), use_container_width=True, height=150)

                if st.button("데이터 병합 실행", type="primary"):
                    if '성명' not in df_new.columns:
                        st.error("필수 컬럼 '성명'이 없습니다.")
                    else:
                        current_cols = st.session_state.df.columns
                        for col in current_cols:
                            if col not in df_new.columns:
                                df_new[col] = None 
                        
                        df_new = df_new[current_cols]
                        
                        date_cols = ['입사일', '최근_직무교육일', '최근_특수검진일']
                        for col in date_cols:
                            df_new[col] = pd.to_datetime(df_new[col], errors='coerce').dt.date
                        
                        bool_cols = [c for c in current_cols if '이수' in c or '4H' in c or '8H' in c or '여부' in c]
                        for col in bool_cols:
                            df_new[col] = df_new[col].fillna(False).astype(bool)

                        st.session_state.df = pd.concat([st.session_state.df, df_new], ignore_index=True)
                        st.success(f"{len(df_new)}명 등록 완료!")
                        st.rerun()

            except Exception as e:
                st.error(f"파일 읽기 오류: {e}")

    st.markdown("### 📝 근로자 명부 수정")
    edited_df = st.data_editor(
        st.session_state.df,
        num_rows="dynamic",
        use_container_width=True,
        key="main_editor",
        column_config={
            "퇴사여부": st.column_config.CheckboxColumn("퇴사", default=False),
            "성명": st.column_config.TextColumn("성명", required=True),
            "직책": st.column_config.SelectboxColumn("직책", options=ROLES),
            "부서": st.column_config.SelectboxColumn("부서", options=DEPTS_LIST),
            "입사일": st.column_config.DateColumn("입사일", format="YYYY-MM-DD"),
            "최근_직무교육일": st.column_config.DateColumn("최근 직무교육일"),
            "신규교육_이수": None, "특별_공통_8H": None, "특별_1_이론_4H": None,
            "특별_1_실습_4H": None, "특별_2_이론_4H": None, "특별_2_실습_4H": None,
            "검진단계": None, "최근_특수검진일": None
        }
    )
    if not st.session_state.df.equals(edited_df):
        st.session_state.df = edited_df

# --- [6. 탭 화면 구성 - 안정적인 업데이트 로직] ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["👔 책임자/감독자", "♻️ 폐기물 담당자", "🌱 신규 입사자", "⚠️ 특별교육", "🏥 특수건강검진"])

def safe_update_from_editor(subset_view, editor_key, visible_cols):
    view_with_no = subset_view.copy()
    view_with_no.insert(0, "No", range(1, len(view_with_no) + 1))
    
    edited_subset = st.data_editor(
        view_with_no,
        key=editor_key,
        use_container_width=True,
        hide_index=True,
        column_config=visible_cols,
        disabled=["No"]
    )
    
    edited_data_only = edited_subset.drop(columns=["No"])
    subset_data_only = subset_view[edited_data_only.columns]
    
    if not subset_data_only.equals(edited_data_only):
        st.session_state.df.update(edited_data_only)

with tab1:
    st.subheader("안전보건관리책임자 / 관리감독자")
    target = dashboard_df[dashboard_df['직책'].isin(['안전보건관리책임자', '관리감독자'])].copy()
    if not target.empty:
        target['상태'] = target.apply(lambda r: "기한초과" if pd.isna(r['다음_직무교육일']) or (r['다음_직무교육일'] - today).days < 0 else ("임박" if (r['다음_직무교육일'] - today).days < 30 else "양호"), axis=1)
        cols_config = {
            "No": st.column_config.NumberColumn("No", width="small"),
            "성명": st.column_config.TextColumn("성명", disabled=True),
            "직책": st.column_config.TextColumn("직책", disabled=True),
            "최근_직무교육일": st.column_config.DateColumn("최근 직무교육일"),
            "다음_직무교육일": st.column_config.DateColumn("다음 예정일", disabled=True),
            "상태": st.column_config.TextColumn("상태", width="small", disabled=True)
        }
        safe_update_from_editor(target[['성명', '직책', '최근_직무교육일', '다음_직무교육일', '상태']], "editor_mgr", cols_config)
    else: st.info("대상자가 없습니다.")

with tab2:
    st.subheader("폐기물 담당자")
    target = dashboard_df[dashboard_df['직책'] == '폐기물담당자'].copy()
    if not target.empty:
        target['상태'] = target.apply(lambda r: "교육필요" if pd.isna(r['다음_직무교육일']) else ("기한초과" if (r['다음_직무교육일'] - today).days < 0 else "양호"), axis=1)
        cols_config = {
            "No": st.column_config.NumberColumn("No", width="small"),
            "성명": st.column_config.TextColumn("성명", disabled=True),
            "부서": st.column_config.TextColumn("부서", disabled=True),
            "최근_직무교육일": st.column_config.DateColumn("최근 직무교육일"),
            "다음_직무교육일": st.column_config.DateColumn("다음 예정일", disabled=True),
            "상태": st.column_config.TextColumn("상태", width="small", disabled=True)
        }
        safe_update_from_editor(target[['성명', '부서', '최근_직무교육일', '다음_직무교육일', '상태']], "editor_waste", cols_config)
    else: st.info("대상자가 없습니다.")

with tab3:
    st.subheader("신규 입사자")
    try: selected_year = st.pills("조회 연도", [today.year, today.year-1], default=today.year)
    except: selected_year = st.radio("조회 연도", [today.year, today.year-1], horizontal=True)
    target = dashboard_df[dashboard_df['입사연도'] == selected_year].copy()
    if not target.empty:
        cols_config = {
            "No": st.column_config.NumberColumn("No", width="small"),
            "신규교육_이수": st.column_config.CheckboxColumn("이수", width="small"),
            "성명": st.column_config.TextColumn("성명", disabled=True),
            "입사일": st.column_config.DateColumn("입사일", disabled=True),
            "부서": st.column_config.TextColumn("부서", disabled=True)
        }
        safe_update_from_editor(target[['신규교육_이수', '성명', '입사일', '부서']], "editor_new", cols_config)
    else: st.info("대상자가 없습니다.")

with tab4:
    st.subheader("특별안전보건교육")
    target = dashboard_df[dashboard_df['특별교육_과목1'] != '해당없음'].copy()
    if not target.empty:
        target.loc[target['법적_신규자'], '특별_공통_8H'] = True
        cols_config = {
            "No": st.column_config.NumberColumn("No", width="small"),
            "성명": st.column_config.TextColumn("성명", disabled=True),
            "부서": st.column_config.TextColumn("부서", disabled=True),
            "법적_신규자": st.column_config.CheckboxColumn("신규", disabled=True, width="small"),
            "특별_공통_8H": st.column_config.CheckboxColumn("공통8H", width="small"),
            "특별교육_과목1": st.column_config.TextColumn("과목1", disabled=True),
            "특별_1_이론_4H": st.column_config.CheckboxColumn("이론4H", width="small"),
            "특별_1_실습_4H": st.column_config.CheckboxColumn("실습4H", width="small"),
            "특별교육_과목2": st.column_config.TextColumn("과목2", disabled=True),
            "특별_2_이론_4H": st.column_config.CheckboxColumn("이론4H", width="small"),
            "특별_2_실습_4H": st.column_config.CheckboxColumn("실습4H", width="small")
        }
        display_cols = ["성명", "부서", "법적_신규자", "특별_공통_8H", "특별교육_과목1", "특별_1_이론_4H", "특별_1_실습_4H", "특별교육_과목2", "특별_2_이론_4H", "특별_2_실습_4H"]
        safe_update_from_editor(target[display_cols], "editor_special", cols_config)
    else: st.info("대상자가 없습니다.")

with tab5:
    st.subheader("특수건강검진")
    target = dashboard_df[(dashboard_df['유해인자'].notna()) & (dashboard_df['유해인자'] != '없음')].copy()
    if not target.empty:
        target['상태'] = target.apply(lambda r: "검진필요" if r['검진단계'] == "배치전(미실시)" else ("-" if pd.isna(r['다음_특수검진일']) else ("기한초과" if (r['다음_특수검진일'] - today).days < 0 else "양호")), axis=1)
        cols_config = {
            "No": st.column_config.NumberColumn("No", width="small"),
            "성명": st.column_config.TextColumn("성명", disabled=True),
            "부서": st.column_config.TextColumn("부서", disabled=True),
            "유해인자": st.column_config.TextColumn("유해인자", disabled=True),
            "검진단계": st.column_config.SelectboxColumn("검진단계", options=HEALTH_PHASES, required=True),
            "최근_특수검진일": st.column_config.DateColumn("최근 검진일"),
            "다음_특수검진일": st.column_config.DateColumn("다음 예정일", disabled=True),
            "상태": st.column_config.TextColumn("상태", width="small", disabled=True)
        }
        safe_update_from_editor(target[["성명", "부서", "유해인자", "검진단계", "최근_특수검진일", "다음_특수검진일", "상태"]], "editor_health", cols_config)
    else: st.info("대상자가 없습니다.")
