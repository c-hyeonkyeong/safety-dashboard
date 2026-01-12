import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from github import Github
import io

# --- [1. 시스템 설정] ---
st.set_page_config(page_title="안전보건 대시보드 Pro", layout="wide", page_icon="🛡️", initial_sidebar_state="expanded")

# CSS: PC 사이드바 너비 및 메트릭 폰트 설정
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

# ==========================================
# [0. 공통 함수 및 설정]
# ==========================================
SPECIAL_EDU_OPTIONS = ["해당없음", "4. 폭발성·물반응성...", "35. 허가 및 관리 대상..."]
ROLES = ["안전보건관리책임자", "관리감독자", "폐기물담당자", "일반근로자"]
HEALTH_PHASES = ["배치전(미실시)", "1차검진 완료(다음:6개월)", "정기검진(다음:1년)"]

def calculate_job_training_date(row):
    last_date = row.get('최근_직무교육일')
    if pd.isna(last_date): return None
    last_date = pd.to_datetime(last_date)
    role = str(row.get('직책', '')).replace(" ", "")
    if '책임자' in role: return last_date + timedelta(days=730)
    elif '폐기물' in role: return last_date + timedelta(days=1095)
    elif '감독자' in role: return last_date + timedelta(days=365)
    return None

def get_dday_status(target_date):
    if pd.isna(target_date): return "-"
    diff = (pd.to_datetime(target_date).date() - date.today()).days
    if diff < 0: return "🔴 초과"
    elif diff < 30: return "🟡 임박"
    return "🟢 양호"

# ==========================================
# [1. 데이터 초기화]
# ==========================================
if 'df_final' not in st.session_state:
    # 기본 샘플 데이터 구조
    st.session_state.df_final = pd.DataFrame({
        '성명': ['김철수'], '직책': ['안전보건관리책임자'], '부서': ['일반관리팀'],
        '입사일': [pd.to_datetime('2022-01-01')], '최근_직무교육일': [pd.to_datetime('2023-05-01')],
        '신규교육_이수': [True], '퇴사여부': [False], '특수검진_대상': [True],
        '검진단계': ['배치전(미실시)'], '최근_특수검진일': [None],
        '공통8H': [False], '과목1_온라인4H': [False], '과목1_감독자4H': [False],
        '과목2_온라인4H': [False], '과목2_감독자4H': [False]
    })

if 'dept_config_final' not in st.session_state:
    st.session_state.dept_config_final = pd.DataFrame({
        '부서명': ['용접팀', '일반관리팀'], '특별교육과목1': ['해당없음', '해당없음'],
        '특별교육과목2': ['해당없음', '해당없음'], '유해인자': ['용접흄', '없음'], '담당관리감독자': ['-', '-']
    })

# ==========================================
# [사이드바] 관리자 메뉴
# ==========================================
with st.sidebar:
    st.header("⚙️ 관리자 설정")
    
    # --- GitHub 연동 섹션 ---
    with st.expander("☁️ GitHub 연동 (저장/불러오기)", expanded=True):
        token = st.text_input("🔑 토큰", type="password")
        repo_path = st.text_input("📂 레포지토리 (user/repo)")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📂 불러오기"):
                try:
                    repo = Github(token).get_repo(repo_path)
                    content = repo.get_contents("data.csv").decoded_content.decode("utf-8")
                    df_load = pd.read_csv(io.StringIO(content))
                    # 날짜 형식 강제 변환
                    for c in ['입사일', '최근_직무교육일', '최근_특수검진일']:
                        if c in df_load.columns: df_load[c] = pd.to_datetime(df_load[c])
                    st.session_state.df_final = df_load
                    st.toast("GitHub에서 데이터를 가져왔습니다!", icon="✅")
                    st.rerun()
                except Exception as e: st.error(f"실패: {e}")
        
        with col2:
            if st.button("💾 저장하기", type="primary"):
                try:
                    repo = Github(token).get_repo(repo_path)
                    # 저장 전 날짜를 문자열로 변환한 복사본 생성
                    df_to_save = st.session_state.df_final.copy()
                    for c in ['입사일', '최근_직무교육일', '최근_특수검진일']:
                        if c in df_to_save.columns:
                            df_to_save[c] = df_to_save[c].dt.strftime('%Y-%m-%d').fillna('')
                    
                    csv_data = df_to_save.to_csv(index=False)
                    try:
                        contents = repo.get_contents("data.csv")
                        repo.update_file("data.csv", f"update {datetime.now()}", csv_data, contents.sha)
                    except:
                        repo.create_file("data.csv", "init", csv_data)
                    st.toast("GitHub 저장 완료!", icon="🚀")
                except Exception as e: st.error(f"저장 실패: {e}")

    # --- 명부 관리 섹션 (완벽 로직 적용) ---
    with st.expander("📝 근로자 명부 수정", expanded=True):
        st.caption("새 행을 추가하거나 데이터를 수정한 후 반드시 아래 '적용' 버튼을 누르세요.")
        
        # 편집기에서 현재 세션 상태의 데이터를 보여줌
        with st.form("worker_edit_form"):
            edited_df = st.data_editor(
                st.session_state.df_final,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "직책": st.column_config.SelectboxColumn(options=ROLES),
                    "부서": st.column_config.SelectboxColumn(options=list(st.session_state.dept_config_final['부서명'])),
                    "검진단계": st.column_config.SelectboxColumn(options=HEALTH_PHASES),
                    "입사일": st.column_config.DateColumn(),
                    "최근_직무교육일": st.column_config.DateColumn(),
                    "최근_특수검진일": st.column_config.DateColumn()
                }
            )
            
            if st.form_submit_button("✅ 명부 수정사항 적용"):
                # 1. 전체 데이터프레임을 편집된 내용으로 완전히 교체 (신규 행 포함)
                st.session_state.df_final = edited_df.copy()
                
                # 2. 날짜 컬럼들이 문자열로 변하지 않도록 강제 datetime 변환
                date_cols = ['입사일', '최근_직무교육일', '최근_특수검진일']
                for col in date_cols:
                    if col in st.session_state.df_final.columns:
                        st.session_state.df_final[col] = pd.to_datetime(st.session_state.df_final[col], errors='coerce')
                
                st.toast("명부가 대시보드에 반영되었습니다! 이제 '저장하기'를 눌러 GitHub에 올릴 수 있습니다.")
                st.rerun()

# ==========================================
# [메인 화면] 대시보드 및 계산 로직
# ==========================================
st.title("🛡️ 산업안전보건 통합 관리 시스템")

# 실시간 계산 로직 (수정된 df_final 기준)
main_df = st.session_state.df_final.copy()
dept_map = st.session_state.dept_config_final.set_index('부서명')

# 부서 기반 특별교육/유해인자 매핑
main_df['특별교육_과목1'] = main_df['부서'].map(dept_map['특별교육과목1']).fillna("해당없음")
main_df['유해인자'] = main_df['부서'].map(dept_map['유해인자']).fillna("없음")

# 다음 교육일 및 검진일 계산
main_df['다음_직무교육일'] = main_df.apply(calculate_job_training_date, axis=1)

# 대시보드 상단 메트릭
active_df = main_df[main_df['퇴사여부'] == False]
c1, c2, c3 = st.columns(3)
c1.metric("👥 현재 인원", f"{len(active_df)}명")
c2.metric("🏥 검진 대상", f"{len(active_df[active_df['특수검진_대상']==True])}명")
c3.metric("👔 관리감독자", f"{len(active_df[active_df['직책']=='관리감독자'])}명")

# 탭 구성
t1, t2 = st.tabs(["📋 전체 명부 현황", "🏥 특수건강검진"])

with t1:
    st.subheader("최신 근로자 명부 (계산 결과 포함)")
    display_df = active_df.copy()
    if not display_df.empty:
        display_df['교육상태'] = display_df['다음_직무교육일'].apply(get_dday_status)
        st.dataframe(display_df, use_container_width=True)

with t2:
    st.subheader("특수건강검진 관리")
    health_df = active_df[active_df['특수검진_대상'] == True].copy()
    if not health_df.empty:
        st.dataframe(health_df[['성명', '부서', '유해인자', '검진단계', '최근_특수검진일']], use_container_width=True)
    else:
        st.info("대상자가 없습니다.")
