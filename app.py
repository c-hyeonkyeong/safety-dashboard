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
    .st-emotion-cache-16idsys p {font-size: 1.1rem;}
</style>
""", unsafe_allow_html=True)

st.title("🏗️ 산업안전보건 통합 관리 시스템")
st.caption("특별교육 탭의 컬럼 순서와 명칭을 재구성하고, 특수검진 탭을 정리했습니다.")

# ==========================================
# [GitHub 연동 설정]
# ==========================================
GITHUB_TOKEN = st.sidebar.text_input("🔑 GitHub 토큰", type="password")
REPO_NAME = st.sidebar.text_input("📂 레포지토리 (user/repo)")
DATA_FILE = "data.csv"
CONFIG_FILE = "config.csv"

def get_github_repo():
    if not GITHUB_TOKEN or not REPO_NAME:
        return None
    try:
        g = Github(GITHUB_TOKEN)
        return g.get_repo(REPO_NAME)
    except Exception as e:
        st.error(f"GitHub 연결 실패: {e}")
        return None

def save_all_to_github(data_df, config_df):
    repo = get_github_repo()
    if not repo: 
        st.sidebar.error("토큰과 레포지토리를 확인해주세요.")
        return
    
    try:
        # 1. 데이터 저장
        data_content = data_df.to_csv(index=False)
        try:
            contents = repo.get_contents(DATA_FILE)
            repo.update_file(DATA_FILE, f"Update data: {datetime.now()}", data_content, contents.sha)
        except:
            repo.create_file(DATA_FILE, "Init data", data_content)
            
        # 2. 설정 저장
        config_content = config_df.to_csv(index=False)
        try:
            contents = repo.get_contents(CONFIG_FILE)
            repo.update_file(CONFIG_FILE, f"Update config: {datetime.now()}", config_content, contents.sha)
        except:
            repo.create_file(CONFIG_FILE, "Init config", config_content)

        st.toast("✅ GitHub 저장 완료!", icon="💾")
    except Exception as e:
        st.sidebar.error(f"❌ 저장 실패: {e}")

def load_all_from_github():
    repo = get_github_repo()
    if not repo: return None, None
    
    loaded_data = None
    loaded_config = None
    
    try:
        contents = repo.get_contents(DATA_FILE)
        csv_string = contents.decoded_content.decode("utf-8")
        loaded_data = pd.read_csv(io.StringIO(csv_string))
        date_cols = ['입사일', '최근_직무교육일', '최근_특수검진일']
        for col in date_cols:
            if col in loaded_data.columns:
                loaded_data[col] = pd.to_datetime(loaded_data[col], errors='coerce').dt.date
    except:
        pass

    try:
        contents = repo.get_contents(CONFIG_FILE)
        csv_string = contents.decoded_content.decode("utf-8")
        loaded_config = pd.read_csv(io.StringIO(csv_string))
    except:
        pass
        
    return loaded_data, loaded_config

# --- [2. 사용자 설정 (관리자 메뉴) - 마우스 정렬 적용] ---
with st.expander("⚙️ [관리자 메뉴] 부서별 교육 및 유해인자 매핑 설정", expanded=False):
    if 'dept_config' not in st.session_state:
        st.session_state.dept_config = pd.DataFrame({
            '부서명': ['용접팀', '전기팀', '밀폐작업팀', '일반관리팀'],
            '특별교육과목1': ['아크용접 등 화기작업', '고압 전기 취급 작업', '밀폐공간 내부 작업', '해당없음'],
            '특별교육과목2': ['그라인더 작업', '해당없음', '해당없음', '해당없음'],
            '유해인자': ['용접흄, 분진', '전류(감전)', '산소결핍', '없음']
        })
    
    req_cols = ['부서명', '특별교육과목1', '특별교육과목2', '유해인자']
    for col in req_cols:
        if col not in st.session_state.dept_config.columns:
            st.session_state.dept_config[col] = '해당없음'

    current_depts = st.session_state.dept_config['부서명'].tolist()
    st.info("👇 아래 박스에서 부서 태그를 마우스로 드래그하여 순서를 변경하세요.")
    
    new_order = st.multiselect(
        "부서 표시 순서 (왼쪽이 최상단)",
        options=current_depts,
        default=current_depts
    )
    
    if new_order:
        config_dict = st.session_state.dept_config.set_index('부서명').to_dict('index')
        new_data = []
        for dept in new_order:
            if dept in config_dict:
                row = config_dict[dept]
                row['부서명'] = dept
                new_data.append(row)
        st.session_state.dept_config = pd.DataFrame(new_data)
        
    edited_dept_config = st.data_editor(
        st.session_state.dept_config, 
        num_rows="dynamic", 
        key="dept_editor", 
        use_container_width=True,
        column_config={
            "부서명": st.column_config.TextColumn("부서명 (순서 변경은 위 박스 이용)"),
            "특별교육과목1": st.column_config.TextColumn("특별교육 과목 1"),
            "특별교육과목2": st.column_config.TextColumn("특별교육 과목 2 (선택)"),
        }
    )
    st.session_state.dept_config = edited_dept_config
    
    DEPT_SUB1_MAP = dict(zip(edited_dept_config['부서명'], edited_dept_config['특별교육과목1']))
    DEPT_SUB2_MAP = dict(zip(edited_dept_config['부서명'], edited_dept_config['특별교육과목2']))
    DEPT_FACTOR_MAP = dict(zip(edited_dept_config['부서명'], edited_dept_config['유해인자']))
    DEPTS_LIST = list(edited_dept_config['부서명'])

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

required_columns = ['퇴사여부', '신규교육_이수', '특별_공통_8H', '특별_1_이론_4H', '특별_1_실습_4H', '특별_2_이론_4H', '특별_2_실습_4H']
for col in required_columns:
    if col not in st.session_state.df.columns:
        st.session_state.df[col] = False

# --- [4. 데이터 입력 및 저장 (사이드바)] ---
with st.sidebar:
    st.header("📝 기본 정보 관리")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📂 불러오기"):
            ld, lc = load_all_from_github()
            if ld is not None: st.session_state.df = ld
            if lc is not None: st.session_state.dept_config = lc
            st.rerun()
    with col2:
        if st.button("💾 저장하기", type="primary"):
            save_all_to_github(st.session_state.df, st.session_state.dept_config)
            
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
            # 나머지 숨김
            "최근_직무교육일": st.column_config.DateColumn("최근 직무교육일"), 
            "신규교육_이수": None, "특별_공통_8H": None,
            "특별_1_이론_4H": None, "특별_1_실습_4H": None,
            "특별_2_이론_4H": None, "특별_2_실습_4H": None,
            "검진단계": None, "최근_특수검진일": None
        }
    )
    st.session_state.df = edited_df.copy()

# --- [5. 로직 계산] ---
df = st.session_state.df.copy()
today = date.today()

# 1. 자동 매핑
df['특별교육_과목1'] = df['부서'].map(DEPT_SUB1_MAP).fillna("설정필요")
df['특별교육_과목2'] = df['부서'].map(DEPT_SUB2_MAP).fillna("해당없음")
df['유해인자'] = df['부서'].map(DEPT_FACTOR_MAP).fillna("확인필요")

# 2. 날짜 유틸 & 신규자 판단
def add_days(d, days):
    if pd.isna(d) or d == "": return None
    return d + timedelta(days=days)

df['입사일_dt'] = pd.to_datetime(df['입사일'], errors='coerce')
df['입사연도'] = df['입사일_dt'].dt.year
df['법적_신규자'] = df['입사일_dt'].apply(lambda x: (pd.Timestamp(today) - x).days < 90 if pd.notnull(x) else False)

# 3. 주기 계산
df['다음_직무교육일'] = None
mask_manager = df['직책'] == '안전보건관리책임자'
df.loc[mask_manager, '다음_직무교육일'] = df[mask_manager]['최근_직무교육일'].apply(lambda x: add_days(x, 730))
mask_supervisor = df['직책'] == '관리감독자'
df.loc[mask_supervisor, '다음_직무교육일'] = df[mask_supervisor]['최근_직무교육일'].apply(lambda x: add_days(x, 365))
mask_waste = df['직책'] == '폐기물담당자'
df.loc[mask_waste, '다음_직무교육일'] = df[mask_waste]['최근_직무교육일'].apply(lambda x: add_days(x, 1095))

# 4. 특수검진 주기
def calc_next_health(row):
    if row['유해인자'] in ['없음', 'None', '', None]: return None
    status = row['검진단계']
    if status == "배치전(미실시)": return None 
    if pd.isna(row['최근_특수검진일']): return None
    cycle = 180 if status == "1차검진 완료(다음:6개월)" else 365
    return row['최근_특수검진일'] + timedelta(days=cycle)

df['다음_특수검진일'] = df.apply(calc_next_health, axis=1)

# 대시보드용
dashboard_df = df[df['퇴사여부'] == False].copy()

def add_numbering(dataframe):
    df_numbered = dataframe.reset_index(drop=True)
    df_numbered.insert(0, 'No', df_numbered.index + 1)
    return df_numbered

# --- [6. 탭 화면 구성] ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "👔 책임자/감독자", "♻️ 폐기물 담당자", "🌱 신규 입사자 현황", "⚠️ 특별교육", "🏥 특수건강검진"
])

with tab1:
    st.subheader("안전보건관리책임자(2년) / 관리감독자(1년)")
    target = dashboard_df[dashboard_df['직책'].isin(['안전보건관리책임자', '관리감독자'])]
    alert_manager = target[target['다음_직무교육일'] < today + timedelta(days=30)]
    if not alert_manager.empty: st.error(f"🚨 교육 기한 임박: {len(alert_manager)}명")
    target_display = add_numbering(target[['성명', '직책', '최근_직무교육일', '다음_직무교육일']])
    st.dataframe(target_display, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("폐기물 담당자 (3년 주기)")
    target = dashboard_df[dashboard_df['직책'] == '폐기물담당자']
    def check_waste_status(row):
        if pd.isna(row['다음_직무교육일']): return "교육필요"
        days_left = (row['다음_직무교육일'] - today).days
        if days_left < 0: return "❌ 기한초과"
        return f"✅ 양호 ({days_left}일)"
    if not target.empty:
        target_display = target.copy()
        target_display['상태'] = target_display.apply(check_waste_status, axis=1)
        final_view = add_numbering(target_display[['성명', '부서', '최근_직무교육일', '다음_직무교육일', '상태']])
        st.dataframe(final_view, use_container_width=True, hide_index=True)
    else:
        st.info("폐기물 담당자가 없습니다.")

with tab3:
    st.subheader("신규 입사자 현황 및 교육 관리")
    current_year = today.year
    recent_years = [current_year, current_year-1, current_year-2]
    selected_year = st.selectbox("입사 연도 선택", recent_years)
    mask_new = dashboard_df['입사연도'] == selected_year
    new_hire_view = dashboard_df[mask_new]
    
    if new_hire_view.empty:
        st.info(f"{selected_year}년도 입사자가 없습니다.")
    else:
        new_hire_view = add_numbering(new_hire_view)
        edited_new_hires = st.data_editor(
            new_hire_view,
            key="editor_new_hire",
            use_container_width=True,
            hide_index=True,
            column_config={
                "No": st.column_config.NumberColumn("No", width="small", disabled=True),
                "신규교육_이수": st.column_config.CheckboxColumn("신규교육 이수", help="교육 완료 시 체크"),
                "성명": st.column_config.TextColumn("성명", disabled=True),
                "입사일": st.column_config.DateColumn("입사일", disabled=True),
                "부서": st.column_config.TextColumn("부서", disabled=True),
                # 숨김
                "직책": None, "최근_직무교육일": None, "퇴사여부": None,
                "특별_공통_8H": None, "특별_1_이론_4H": None, "특별_1_실습_4H": None,
                "특별_2_이론_4H": None, "특별_2_실습_4H": None,
                "검진단계": None, "최근_특수검진일": None, "특별교육_과목1": None, 
                "특별교육_과목2": None, "유해인자": None, "입사일_dt": None, 
                "입사연도": None, "법적_신규자": None, "다음_직무교육일": None, "다음_특수검진일": None
            }
        )
        if not new_hire_view.equals(edited_new_hires):
            cols_to_update = ['신규교육_이수']
            for index, row in edited_new_hires.iterrows():
                name = row['성명']
                idx = st.session_state.df[st.session_state.df['성명'] == name].index
                if not idx.empty:
                    st.session_state.df.loc[idx, '신규교육_이수'] = row['신규교육_이수']
            st.rerun()

with tab4:
    st.subheader("특별안전보건교육 이수 관리 (세분화)")
    st.info("💡 신규 입사자는 공통(8H)이 자동으로 체크됩니다. (신규교육으로 갈음)")
    
    mask_special = dashboard_df['특별교육_과목1'] != '해당없음'
    special_view = dashboard_df[mask_special].copy()
    
    if special_view.empty:
        st.info("특별교육 대상자가 없습니다.")
    else:
        # ★ [로직] 신규 입사자일 경우 '특별_공통_8H'를 True로 강제 (갈음 처리)
        # 뷰 생성 시점에는 강제로 True로 보여주고, 사용자가 체크 시 원본 데이터 업데이트
        
        # 1. 신규 입사자라면 특별_공통_8H 값을 True로 덮어씌운 뷰 생성
        special_view.loc[special_view['법적_신규자'] == True, '특별_공통_8H'] = True
        
        special_view = add_numbering(special_view)
        
        # 컬럼 순서 지정
        col_order = [
            "No", "성명", "부서", "법적_신규자", "특별_공통_8H", 
            "특별교육_과목1", "특별_1_이론_4H", "특별_1_실습_4H",
            "특별교육_과목2", "특별_2_이론_4H", "특별_2_실습_4H"
        ]
        
        edited_special = st.data_editor(
            special_view,
            key="editor_special",
            use_container_width=True,
            hide_index=True,
            column_order=col_order, # ★ 요청하신 순서 적용
            column_config={
                "No": st.column_config.NumberColumn("No", width="small", disabled=True),
                "성명": st.column_config.TextColumn("성명", disabled=True),
                "부서": st.column_config.TextColumn("부서", disabled=True),
                
                # 요청하신 명칭 적용
                "법적_신규자": st.column_config.CheckboxColumn("신규 입사자", disabled=True),
                "특별_공통_8H": st.column_config.CheckboxColumn("공통8H"),
                
                "특별교육_과목1": st.column_config.TextColumn("과목1", disabled=True),
                "특별_1_이론_4H": st.column_config.CheckboxColumn("과목1_온라인4H"),
                "특별_1_실습_4H": st.column_config.CheckboxColumn("과목1_관리감독자4H"),
                
                "특별교육_과목2": st.column_config.TextColumn("과목2", disabled=True),
                "특별_2_이론_4H": st.column_config.CheckboxColumn("과목2_온라인4H"),
                "특별_2_실습_4H": st.column_config.CheckboxColumn("과목2_관리감독자"),
                
                # 나머지 숨김
                "직책": None, "입사일": None, "퇴사여부": None, "최근_직무교육일": None,
                "신규교육_이수": None, "검진단계": None, "최근_특수검진일": None, "유해인자": None,
                "입사일_dt": None, "입사연도": None, "다음_직무교육일": None, "다음_특수검진일": None
            }
        )
        
        if not special_view.equals(edited_special):
            # 업데이트 시, 공통8H는 신규 입사자가 아닌 경우에만 의미가 있으나,
            # 사용자가 체크한 그대로 저장 (신규 입사자 자동체크된 것도 저장됨)
            cols_check = ['특별_공통_8H', '특별_1_이론_4H', '특별_1_실습_4H', '특별_2_이론_4H', '특별_2_실습_4H']
            for index, row in edited_special.iterrows():
                name = row['성명']
                idx = st.session_state.df[st.session_state.df['성명'] == name].index
                if not idx.empty:
                    st.session_state.df.loc[idx, cols_check] = row[cols_check]
            st.rerun()

with tab5:
    st.subheader("특수건강검진 관리")
    
    mask_health = (dashboard_df['유해인자'].notna()) & (dashboard_df['유해인자'] != '없음')
    health_view = dashboard_df[mask_health].copy()
    
    if health_view.empty:
        st.info("특수검진 대상자가 없습니다.")
    else:
        def get_status_label(row):
            if row['검진단계'] == "배치전(미실시)": return "🚨 배치전필요"
            if pd.isna(row['다음_특수검진일']): return "-"
            days = (row['다음_특수검진일'] - today).days
            if days < 0: return "❌ 기한초과"
            if days < 30: return "⚠️ 임박"
            return "✅ 양호"

        health_view['현재상태'] = health_view.apply(get_status_label, axis=1)
        health_view = add_numbering(health_view)

        edited_health = st.data_editor(
            health_view,
            key="editor_health",
            use_container_width=True,
            hide_index=True,
            column_config={
                "No": st.column_config.NumberColumn("No", width="small", disabled=True),
                "성명": st.column_config.TextColumn("성명", disabled=True),
                "부서": st.column_config.TextColumn("부서", disabled=True),
                "유해인자": st.column_config.TextColumn("유해인자", disabled=True),
                "검진단계": st.column_config.SelectboxColumn("검진단계", options=HEALTH_PHASES, required=True),
                "최근_특수검진일": st.column_config.DateColumn("최근 검진일"),
                "다음_특수검진일": st.column_config.DateColumn("다음 예정일", disabled=True),
                "현재상태": st.column_config.TextColumn("상태", disabled=True),
                # ★ 중요: 교육 관련 컬럼 확실하게 숨김
                "직책": None, "입사일": None, "퇴사여부": None, "최근_직무교육일": None,
                "신규교육_이수": None, "특별_공통_8H": None, "특별_1_이론_4H": None, 
                "특별_1_실습_4H": None, "특별_2_이론_4H": None, "특별_2_실습_4H": None,
                "특별교육_과목1": None, "특별교육_과목2": None, "입사일_dt": None, 
                "입사연도": None, "법적_신규자": None, "다음_직무교육일": None
            }
        )
        
        if not health_view.equals(edited_health):
            cols_to_update = ['검진단계', '최근_특수검진일']
            for index, row in edited_health.iterrows():
                name = row['성명']
                idx = st.session_state.df[st.session_state.df['성명'] == name].index
                if not idx.empty:
                    st.session_state.df.loc[idx, cols_to_update] = row[cols_to_update]
            st.rerun()
