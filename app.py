import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from github import Github
import io

# --- [1. 시스템 설정] ---
st.set_page_config(page_title="안전보건 대시보드 Pro", layout="wide", page_icon="🛡️")

# CSS로 디자인 디테일 잡기
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

    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stMarkdownContainer"] p {
        margin-bottom: 0px;
        line-height: 32px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ 산업안전보건 통합 관리 시스템")
st.markdown("---")

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
    if not GITHUB_TOKEN or not REPO_NAME:
        return None
    try:
        g = Github(GITHUB_TOKEN)
        return g.get_repo(REPO_NAME)
    except Exception as e:
        return None

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

        st.toast("✅ 데이터가 안전하게 저장되었습니다!", icon="☁️")
    except Exception as e:
        st.sidebar.error(f"저장 실패: {e}")

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

# --- [2. 사용자 설정 (관리자 메뉴)] ---
if 'dept_config' not in st.session_state:
    st.session_state.dept_config = pd.DataFrame({
        '정렬순서': [1, 2, 3, 4],
        '부서명': ['용접팀', '전기팀', '밀폐작업팀', '일반관리팀'],
        '특별교육과목1': ['아크용접 등 화기작업', '고압 전기 취급 작업', '밀폐공간 내부 작업', '해당없음'],
        '특별교육과목2': ['그라인더 작업', '해당없음', '해당없음', '해당없음'],
        '유해인자': ['용접흄, 분진', '전류(감전)', '산소결핍', '없음']
    })

# 안전장치
for col in ['정렬순서', '부서명', '특별교육과목1', '특별교육과목2', '유해인자']:
    if col not in st.session_state.dept_config.columns:
        if col == '정렬순서':
             st.session_state.dept_config.insert(0, '정렬순서', range(1, len(st.session_state.dept_config) + 1))
        else:
            st.session_state.dept_config[col] = '해당없음'

SPECIAL_EDU_OPTIONS = [
    "해당없음",
    "4. 폭발성·물반응성·자기반응성·자기발열성 물질, 자연발화성 액체·고체 및 인화성 액체의 제조 또는 취급작업",
    "35. 허가 및 관리 대상 유해물질의 제조 또는 취급작업"
]

with st.expander("🛠️ [관리자 설정] 부서 순서 및 교육 매핑", expanded=False):
    st.caption("부서 순서를 변경하고, 각 부서에 해당하는 특별교육 및 유해인자를 설정하세요.")
    
    df_config = st.session_state.dept_config.sort_values('정렬순서').reset_index(drop=True)
    
    with st.container(border=True):
        for i, row in df_config.iterrows():
            c1, c2, c3 = st.columns([8, 1, 1], gap="small", vertical_alignment="center")
            
            with c1:
                st.markdown(f"**{i+1}. {row['부서명']}**")
            with c2:
                if i > 0:
                    if st.button("⬆️", key=f"up_{i}", help="위로 이동"):
                        curr_idx = df_config.at[i, '정렬순서']
                        prev_idx = df_config.at[i-1, '정렬순서']
                        mask_curr = st.session_state.dept_config['정렬순서'] == curr_idx
                        mask_prev = st.session_state.dept_config['정렬순서'] == prev_idx
                        st.session_state.dept_config.loc[mask_curr, '정렬순서'] = 9999
                        st.session_state.dept_config.loc[mask_prev, '정렬순서'] = curr_idx
                        st.session_state.dept_config.loc[mask_curr, '정렬순서'] = prev_idx
                        st.rerun()
            with c3:
                if i < len(df_config) - 1:
                    if st.button("⬇️", key=f"down_{i}", help="아래로 이동"):
                        curr_idx = df_config.at[i, '정렬순서']
                        next_idx = df_config.at[i+1, '정렬순서']
                        mask_curr = st.session_state.dept_config['정렬순서'] == curr_idx
                        mask_next = st.session_state.dept_config['정렬순서'] == next_idx
                        st.session_state.dept_config.loc[mask_curr, '정렬순서'] = 9999
                        st.session_state.dept_config.loc[mask_next, '정렬순서'] = curr_idx
                        st.session_state.dept_config.loc[mask_curr, '정렬순서'] = next_idx
                        st.rerun()
            
            if i < len(df_config) - 1:
                st.markdown('<hr style="margin: 5px 0; border-top: 1px solid #e0e0e0;">', unsafe_allow_html=True)

    st.markdown("#### 📝 매핑 상세 설정")
    sorted_df = st.session_state.dept_config.sort_values('정렬순서')
    
    edited_dept_config = st.data_editor(
        sorted_df,
        num_rows="dynamic", 
        key="dept_editor", 
        use_container_width=True,
        hide_index=True,
        column_config={
            "정렬순서": None,
            "부서명": st.column_config.TextColumn("부서명", required=True),
            "특별교육과목1": st.column_config.SelectboxColumn(
                "특별교육 1", 
                width="large", 
                options=SPECIAL_EDU_OPTIONS,
                required=True
            ),
            "특별교육과목2": st.column_config.SelectboxColumn(
                "특별교육 2", 
                width="large", 
                options=SPECIAL_EDU_OPTIONS,
                required=True
            ),
            "유해인자": st.column_config.TextColumn("유해인자", width="medium"),
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

# --- [4. 메인 대시보드] ---
df = st.session_state.df.copy()
today = date.today()

if 'DEPT_SUB1_MAP' not in locals():
    DEPT_SUB1_MAP = dict(zip(st.session_state.dept_config['부서명'], st.session_state.dept_config['특별교육과목1']))
    DEPT_SUB2_MAP = dict(zip(st.session_state.dept_config['부서명'], st.session_state.dept_config['특별교육과목2']))
    DEPT_FACTOR_MAP = dict(zip(st.session_state.dept_config['부서명'], st.session_state.dept_config['유해인자']))
    DEPTS_LIST = list(st.session_state.dept_config['부서명'])

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
dashboard_df = df[df['퇴사여부'] == False].copy()

# === [상단 요약] ===
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("👥 총 관리 인원", f"{len(dashboard_df)}명")
with col2:
    new_hires = len(dashboard_df[dashboard_df['법적_신규자']])
    st.metric("🌱 신규 입사자", f"{new_hires}명")
with col3:
    managers = len(dashboard_df[dashboard_df['직책'].isin(['안전보건관리책임자', '관리감독자'])])
    st.metric("👔 책임자/감독자", f"{managers}명")
with col4:
    health_target = len(dashboard_df[(dashboard_df['유해인자'].notna()) & (dashboard_df['유해인자'] != '없음')])
    st.metric("🏥 검진 대상", f"{health_target}명")

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

    # --- [추가된 기능] 일괄 업로드 기능 ---
    with st.expander("📂 근로자 명부 일괄 등록 (Excel/CSV)", expanded=False):
        uploaded_file = st.file_uploader("파일 업로드", type=['csv', 'xlsx'])
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_new = pd.read_csv(uploaded_file)
                else:
                    df_new = pd.read_excel(uploaded_file)
                
                # 필수 컬럼 확인
                if '성명' not in df_new.columns:
                    st.error("오류: 파일에 '성명' 컬럼이 있어야 합니다.")
                else:
                    st.write(f"총 {len(df_new)}명 로드됨")
                    if st.button("데이터 병합하기", use_container_width=True):
                        # 기존 컬럼 구조에 맞추기 (없는 컬럼은 기본값 채움)
                        for col in st.session_state.df.columns:
                            if col not in df_new.columns:
                                # 날짜 컬럼은 None, 나머지는 False나 빈 문자열 등 기본값
                                if "일" in col or "날짜" in col:
                                    df_new[col] = None
                                elif "이수" in col or "여부" in col or "8H" in col or "4H" in col:
                                    df_new[col] = False
                                else:
                                    df_new[col] = None
                        
                        # 날짜 변환 (엑셀 datetime -> date)
                        date_cols = ['입사일', '최근_직무교육일', '최근_특수검진일']
                        for col in date_cols:
                            if col in df_new.columns:
                                df_new[col] = pd.to_datetime(df_new[col], errors='coerce').dt.date

                        # 필요한 컬럼만 선택해서 병합
                        df_new = df_new[st.session_state.df.columns]
                        st.session_state.df = pd.concat([st.session_state.df, df_new], ignore_index=True)
                        st.success("성공적으로 추가되었습니다!")
                        st.rerun()
            except Exception as e:
                st.error(f"파일 처리 중 오류 발생: {e}")

    st.markdown("### 📝 근로자 명부 수정")
    st.caption("이름, 직책, 부서, 입사일 등 기본 정보만 여기서 수정하세요.")
    
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
            "신규교육_이수": None, "특별_공통_8H": None,
            "특별_1_이론_4H": None, "특별_1_실습_4H": None,
            "특별_2_이론_4H": None, "특별_2_실습_4H": None,
            "검진단계": None, "최근_특수검진일": None
        }
    )
    st.session_state.df = edited_df.copy()

def add_numbering(dataframe):
    df_numbered = dataframe.reset_index(drop=True)
    df_numbered.insert(0, 'No', df_numbered.index + 1)
    return df_numbered

# --- [6. 탭 화면 구성] ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "👔 책임자/감독자", "♻️ 폐기물 담당자", "🌱 신규 입사자", "⚠️ 특별교육", "🏥 특수건강검진"
])

with tab1:
    st.subheader("안전보건관리책임자 / 관리감독자")
    target = dashboard_df[dashboard_df['직책'].isin(['안전보건관리책임자', '관리감독자'])].copy()
    
    def check_mgr_status(row):
        if pd.isna(row['다음_직무교육일']): return None
        days = (row['다음_직무교육일'] - today).days
        if days < 0: return "기한초과"
        if days < 30: return "임박"
        return "양호"
    
    if not target.empty:
        target['상태'] = target.apply(check_mgr_status, axis=1)
        target_display = add_numbering(target[['성명', '직책', '최근_직무교육일', '다음_직무교육일', '상태']])
        st.dataframe(
            target_display, use_container_width=True, hide_index=True,
            column_config={
                "No": st.column_config.NumberColumn("No", width="small"),
                "상태": st.column_config.TextColumn("상태", width="small")
            }
        )
    else:
        st.info("대상자가 없습니다.")

with tab2:
    st.subheader("폐기물 담당자 (3년 주기)")
    target = dashboard_df[dashboard_df['직책'] == '폐기물담당자'].copy()
    
    def check_waste_status(row):
        if pd.isna(row['다음_직무교육일']): return "교육필요"
        days_left = (row['다음_직무교육일'] - today).days
        if days_left < 0: return "기한초과"
        return "양호"
        
    if not target.empty:
        target['상태'] = target.apply(check_waste_status, axis=1)
        final_view = add_numbering(target[['성명', '부서', '최근_직무교육일', '다음_직무교육일', '상태']])
        st.dataframe(
            final_view, use_container_width=True, hide_index=True,
            column_config={
                "No": st.column_config.NumberColumn("No", width="small"),
                "상태": st.column_config.TextColumn("상태", width="small")
            }
        )
    else:
        st.info("폐기물 담당자가 없습니다.")

with tab3:
    st.subheader("신규 입사자 교육 현황")
    current_year = today.year
    recent_years = [current_year, current_year-1, current_year-2]
    try:
        selected_year = st.pills("조회 연도", recent_years, default=current_year)
    except AttributeError:
        selected_year = st.radio("조회 연도", recent_years, horizontal=True, index=0)
    
    mask_new = dashboard_df['입사연도'] == selected_year
    new_hire_view = dashboard_df[mask_new].copy()
    
    if new_hire_view.empty:
        st.info(f"{selected_year}년도 입사자가 없습니다.")
    else:
        new_hire_view = add_numbering(new_hire_view)
        edited_new_hires = st.data_editor(
            new_hire_view, key="editor_new_hire", use_container_width=True, hide_index=True,
            column_config={
                "No": st.column_config.NumberColumn("No", width="small"),
                "신규교육_이수": st.column_config.CheckboxColumn("교육 이수", width="small"),
                "성명": st.column_config.TextColumn("성명", disabled=True),
                "입사일": st.column_config.DateColumn("입사일", disabled=True),
                "부서": st.column_config.TextColumn("부서", disabled=True),
                "직책": None, "최근_직무교육일": None, "퇴사여부": None,
                "특별_공통_8H": None, "특별_1_이론_4H": None, "특별_1_실습_4H": None,
                "특별_2_이론_4H": None, "특별_2_실습_4H": None,
                "검진단계": None, "최근_특수검진일": None, "특별교육_과목1": None, 
                "특별교육_과목2": None, "유해인자": None, "입사일_dt": None, 
                "입사연도": None, "법적_신규자": None, "다음_직무교육일": None, "다음_특수검진일": None
            }
        )
        if not new_hire_view.equals(edited_new_hires):
            for index, row in edited_new_hires.iterrows():
                name = row['성명']
                idx = st.session_state.df[st.session_state.df['성명'] == name].index
                if not idx.empty:
                    st.session_state.df.loc[idx, '신규교육_이수'] = row['신규교육_이수']
            st.rerun()

with tab4:
    st.subheader("특별안전보건교육")
    st.caption("신규 입사자는 공통(8H)이 자동 이수 처리됩니다.")
    
    mask_special = dashboard_df['특별교육_과목1'] != '해당없음'
    special_view = dashboard_df[mask_special].copy()
    
    if special_view.empty:
        st.info("특별교육 대상자가 없습니다.")
    else:
        special_view.loc[special_view['법적_신규자'] == True, '특별_공통_8H'] = True
        special_view = add_numbering(special_view)
        col_order = [
            "No", "성명", "부서", "법적_신규자", "특별_공통_8H", 
            "특별교육_과목1", "특별_1_이론_4H", "특별_1_실습_4H",
            "특별교육_과목2", "특별_2_이론_4H", "특별_2_실습_4H"
        ]
        edited_special = st.data_editor(
            special_view, key="editor_special", use_container_width=True, hide_index=True, column_order=col_order,
            column_config={
                "No": st.column_config.NumberColumn("No", width="small"),
                "성명": st.column_config.TextColumn("성명", disabled=True),
                "부서": st.column_config.TextColumn("부서", disabled=True),
                "법적_신규자": st.column_config.CheckboxColumn("신규", disabled=True, width="small"),
                "특별_공통_8H": st.column_config.CheckboxColumn("공통8H", width="small"),
                "특별교육_과목1": st.column_config.TextColumn("과목1", disabled=True),
                "특별_1_이론_4H": st.column_config.CheckboxColumn("온라인4H", width="small"),
                "특별_1_실습_4H": st.column_config.CheckboxColumn("감독자4H", width="small"),
                "특별교육_과목2": st.column_config.TextColumn("과목2", disabled=True),
                "특별_2_이론_4H": st.column_config.CheckboxColumn("온라인4H", width="small"),
                "특별_2_실습_4H": st.column_config.CheckboxColumn("감독자4H", width="small"),
                "직책": None, "입사일": None, "퇴사여부": None, "최근_직무교육일": None,
                "신규교육_이수": None, "검진단계": None, "최근_특수검진일": None, "유해인자": None,
                "입사일_dt": None, "입사연도": None, "다음_직무교육일": None, "다음_특수검진일": None
            }
        )
        if not special_view.equals(edited_special):
            cols_check = ['특별_공통_8H', '특별_1_이론_4H', '특별_1_실습_4H', '특별_2_이론_4H', '특별_2_실습_4H']
            for index, row in edited_special.iterrows():
                name = row['성명']
                idx = st.session_state.df[st.session_state.df['성명'] == name].index
                if not idx.empty:
                    st.session_state.df.loc[idx, cols_check] = row[cols_check]
            st.rerun()

with tab5:
    st.subheader("특수건강검진")
    mask_health = (dashboard_df['유해인자'].notna()) & (dashboard_df['유해인자'] != '없음')
    health_view = dashboard_df[mask_health].copy()
    
    if health_view.empty:
        st.info("특수검진 대상자가 없습니다.")
    else:
        def get_status_label(row):
            if row['검진단계'] == "배치전(미실시)": return "검진필요"
            if pd.isna(row['다음_특수검진일']): return "-"
            days = (row['다음_특수검진일'] - today).days
            if days < 0: return "기한초과"
            if days < 30: return "임박"
            return "양호"

        health_view['현재상태'] = health_view.apply(get_status_label, axis=1)
        health_view = add_numbering(health_view)

        edited_health = st.data_editor(
            health_view, key="editor_health", use_container_width=True, hide_index=True,
            column_config={
                "No": st.column_config.NumberColumn("No", width="small"),
                "성명": st.column_config.TextColumn("성명", disabled=True),
                "부서": st.column_config.TextColumn("부서", disabled=True),
                "유해인자": st.column_config.TextColumn("유해인자", disabled=True),
                "검진단계": st.column_config.SelectboxColumn("검진단계", options=HEALTH_PHASES, required=True),
                "최근_특수검진일": st.column_config.DateColumn("최근 검진일"),
                "다음_특수검진일": st.column_config.DateColumn("다음 예정일", disabled=True),
                "현재상태": st.column_config.TextColumn("상태", width="small"),
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
