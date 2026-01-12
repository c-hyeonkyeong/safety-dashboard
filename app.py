import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from github import Github
import io

# --- [1. 시스템 설정] ---
st.set_page_config(page_title="안전보건 대시보드 Pro", layout="wide", page_icon="🛡️", initial_sidebar_state="expanded")

# CSS: PC 사이드바 너비 조정
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
SPECIAL_EDU_OPTIONS = ["해당없음", "4. 폭발성...", "35. 허가 및..."]
ROLES = ["안전보건관리책임자", "관리감독자", "폐기물담당자", "일반근로자"]
HEALTH_PHASES = ["배치전(미실시)", "1차검진 완료(다음:6개월)", "정기검진(다음:1년)"]

# [데이터 동기화 콜백 함수] - 명부가 수정되면 즉시 실행되어 df_final을 업데이트함
def sync_worker_data():
    if "main_editor_sidebar" in st.session_state:
        # data_editor의 변경사항(수정, 추가, 삭제)을 가져옴
        edits = st.session_state["main_editor_sidebar"]
        
        # 1. 기존 데이터프레임 복사
        df = st.session_state.df_final.copy()
        
        # 2. 수정사항 반영 (edited_rows)
        for row_idx, patch in edits.get("edited_rows", {}).items():
            for col, val in patch.items():
                df.iloc[row_idx, df.columns.get_loc(col)] = val
        
        # 3. 추가사항 반영 (added_rows) - 이 부분이 신규 입사자 저장의 핵심!
        added = edits.get("added_rows", [])
        if added:
            new_rows = pd.DataFrame(added)
            df = pd.concat([df, new_rows], ignore_index=True)
        
        # 4. 삭제사항 반영 (deleted_rows)
        deleted = edits.get("deleted_rows", [])
        if deleted:
            df = df.drop(index=deleted).reset_index(drop=True)
            
        # 5. 최종 결과 저장 및 타입 보정
        for col in ['입사일', '최근_직무교육일', '최근_특수검진일']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        st.session_state.df_final = df

# 초기 데이터 로드 (생략 가능하나 구조 유지를 위해 유지)
if 'df_final' not in st.session_state:
    data = {
        '성명': ['김철수', '이영희'],
        '직책': ['안전보건관리책임자', '관리감독자'],
        '부서': ['일반관리팀', '일반관리팀'],
        '입사일': [date(2022, 1, 1), date(2023, 5, 20)],
        '최근_직무교육일': [date(2023, 5, 1), date(2024, 5, 20)],
        '신규교육_이수': [False, False],
        '공통8H': [False, False], '과목1_온라인4H': [False, False], '과목1_감독자4H': [False, False],
        '과목2_온라인4H': [False, False], '과목2_감독자4H': [False, False],
        '검진단계': ['배치전(미실시)', '배치전(미실시)'], 
        '최근_특수검진일': [None, None],
        '특수검진_대상': [True, True] 
    }
    st.session_state.df_final = pd.DataFrame(data)

if 'dept_config_final' not in st.session_state:
    st.session_state.dept_config_final = pd.DataFrame({
        '정렬순서': [1, 2], '부서명': ['용접팀', '일반관리팀'],
        '특별교육과목1': ["해당없음", "해당없음"], '특별교육과목2': ["해당없음", "해당없음"],
        '유해인자': ['용접흄', '없음'], '담당관리감독자': ['-', '-']
    })

# ==========================================
# [사이드바 메뉴]
# ==========================================
with st.sidebar:
    st.header("⚙️ 통합 관리자 메뉴")
    
    # --- 1. GitHub 설정 (최상단) ---
    with st.expander("☁️ GitHub 연동 설정", expanded=True):
        GITHUB_TOKEN = st.text_input("🔑 GitHub 토큰", type="password")
        REPO_NAME = st.text_input("📂 레포지토리 (user/repo)")
        DATA_FILE = "data.csv"
        CONFIG_FILE = "config.csv"

        def get_github_repo():
            if not GITHUB_TOKEN or not REPO_NAME: return None
            try: return Github(GITHUB_TOKEN).get_repo(REPO_NAME)
            except: return None

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("📂 불러오기"):
                repo = get_github_repo()
                if repo:
                    try:
                        contents = repo.get_contents(DATA_FILE)
                        csv_string = contents.decoded_content.decode("utf-8")
                        ld = pd.read_csv(io.StringIO(csv_string))
                        for col in ['입사일', '최근_직무교육일', '최근_특수검진일']:
                            if col in ld.columns: ld[col] = pd.to_datetime(ld[col])
                        st.session_state.df_final = ld
                        st.toast("로드 완료!")
                        st.rerun()
                    except: st.error("파일 로드 실패")

        with col_s2:
            if st.button("💾 저장하기", type="primary"):
                # 저장하기 클릭 시점에 이미 콜백을 통해 df_final이 최신화되어 있음!
                repo = get_github_repo()
                if repo:
                    try:
                        save_df = st.session_state.df_final.copy()
                        for col in ['입사일', '최근_직무교육일', '최근_특수검진일']:
                            if col in save_df.columns:
                                save_df[col] = save_df[col].dt.strftime('%Y-%m-%d')
                        
                        content = save_df.to_csv(index=False)
                        try:
                            file_git = repo.get_contents(DATA_FILE)
                            repo.update_file(DATA_FILE, f"update {datetime.now()}", content, file_git.sha)
                        except:
                            repo.create_file(DATA_FILE, "init", content)
                        st.toast("GitHub 저장 완료!")
                    except Exception as e: st.error(f"저장 실패: {e}")

    st.divider()

    # --- 2. 근로자 명부 관리 (가장 중요한 부분) ---
    with st.expander("📝 근로자 명부 관리", expanded=True):
        view_cols = [
            '성명', '직책', '부서', '입사일', '최근_직무교육일', '신규교육_이수', 
            '특수검진_대상', '검진단계', '최근_특수검진일', '퇴사여부'
        ]
        
        # [핵심] on_change 파라미터에 콜백 함수를 연결하여 실시간 동기화
        st.data_editor(
            st.session_state.df_final,
            num_rows="dynamic",
            key="main_editor_sidebar",
            on_change=sync_worker_data, # 수정/추가 즉시 sync_worker_data 실행
            use_container_width=True,
            column_config={
                "직책": st.column_config.SelectboxColumn(options=ROLES),
                "검진단계": st.column_config.SelectboxColumn(options=HEALTH_PHASES),
                "입사일": st.column_config.DateColumn(),
                "최근_직무교육일": st.column_config.DateColumn(),
                "최근_특수검진일": st.column_config.DateColumn(),
            }
        )

# ==========================================
# [메인 화면 대시보드]
# ==========================================
# 대시보드 로직은 st.session_state.df_final을 기반으로 작동하므로 위에서 동기화된 데이터를 그대로 씁니다.
active_df = st.session_state.df_final[st.session_state.df_final.get('퇴사여부', False) == False]

st.subheader("📊 현재 재직자 현황")
st.dataframe(active_df, use_container_width=True)

if st.button("🔄 화면 새로고침"):
    st.rerun()
