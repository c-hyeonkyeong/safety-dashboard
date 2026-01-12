import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from github import Github
import io

# --- [1. 시스템 설정] ---
st.set_page_config(page_title="안전보건 Pro", layout="wide", initial_sidebar_state="expanded")

# CSS: UI 가독성 향상
st.markdown("""
<style>
    div[data-testid="stMetricValue"] {font-size: 24px; font-weight: bold;}
    div.stButton > button {width: 100%; border-radius: 6px; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# [0. 초기 데이터 및 함수]
# ==========================================
ROLES = ["안전보건관리책임자", "관리감독자", "폐기물담당자", "일반근로자"]
HEALTH_PHASES = ["배치전(미실시)", "1차검진 완료(다음:6개월)", "정기검진(다음:1년)"]

def convert_dates(df):
    """모든 날짜 컬럼을 에러 없이 datetime으로 변환하는 함수"""
    date_cols = ['입사일', '최근_직무교육일', '최근_특수검진일']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df

# 데이터 초기화
if 'df_final' not in st.session_state:
    st.session_state.df_final = pd.DataFrame({
        '성명': ['홍길동'], '직책': ['일반근로자'], '부서': ['용접팀'],
        '입사일': [pd.to_datetime('2024-01-01')], '최근_직무교육일': [pd.NaT],
        '신규교육_이수': [False], '퇴사여부': [False], '특수검진_대상': [True],
        '검진단계': ['배치전(미실시)'], '최근_특수검진일': [pd.NaT],
        '공통8H': [False], '과목1_온라인4H': [False], '과목1_감독자4H': [False],
        '과목2_온라인4H': [False], '과목2_감독자4H': [False]
    })

# ==========================================
# [1. 사이드바 관리자 메뉴]
# ==========================================
with st.sidebar:
    st.header("⚙️ 관리자 설정")
    
    # --- GitHub 연동 섹션 ---
    with st.expander("☁️ GitHub 연동 (저장/불러오기)", expanded=True):
        g_token = st.text_input("🔑 GitHub 토큰", type="password")
        g_repo = st.text_input("📂 레포지토리 (user/repo)")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📂 불러오기"):
                try:
                    repo = Github(g_token).get_repo(g_repo)
                    content = repo.get_contents("data.csv").decoded_content.decode("utf-8")
                    loaded_df = pd.read_csv(io.StringIO(content))
                    st.session_state.df_final = convert_dates(loaded_df)
                    st.success("데이터 로드 완료!")
                    st.rerun()
                except Exception as e: st.error(f"실패: {e}")
        
        with col2:
            if st.button("💾 저장하기", type="primary"):
                # [핵심] 현재 세션에 저장된 최신 df_final을 저장
                try:
                    repo = Github(g_token).get_repo(g_repo)
                    df_to_save = st.session_state.df_final.copy()
                    # 날짜를 문자열로 변환 (저장용)
                    for c in ['입사일', '최근_직무교육일', '최근_특수검진일']:
                        if c in df_to_save.columns:
                            df_to_save[c] = df_to_save[c].dt.strftime('%Y-%m-%d').fillna('')
                    
                    csv_data = df_to_save.to_csv(index=False)
                    try:
                        f_contents = repo.get_contents("data.csv")
                        repo.update_file("data.csv", f"Update: {datetime.now()}", csv_data, f_contents.sha)
                    except:
                        repo.create_file("data.csv", "Initial Commit", csv_data)
                    st.toast("GitHub 저장 성공!", icon="🚀")
                except Exception as e: st.error(f"저장 실패: {e}")

    st.divider()

    # --- 근로자 명부 수정 섹션 ---
    with st.expander("📝 근로자 명부 수정 및 추가", expanded=True):
        st.warning("데이터 수정/행 추가 후 아래 '명부 수정사항 적용'을 꼭 눌러주세요.")
        
        # [핵심] data_editor의 결과를 바로 변수에 할당하지 않고, 폼을 통해 제출받음
        with st.form("worker_management_form"):
            # 세션에 있는 데이터를 편집기에 띄움
            current_df = st.session_state.df_final.copy()
            
            # 편집기 실행
            new_edited_df = st.data_editor(
                current_df,
                num_rows="dynamic", # 행 추가/삭제 가능하게 설정
                use_container_width=True,
                key="editor_widget",
                column_config={
                    "직책": st.column_config.SelectboxColumn(options=ROLES),
                    "검진단계": st.column_config.SelectboxColumn(options=HEALTH_PHASES),
                    "입사일": st.column_config.DateColumn(),
                    "최근_직무교육일": st.column_config.DateColumn(),
                    "최근_특수검진일": st.column_config.DateColumn()
                }
            )
            
            # 적용 버튼
            submit = st.form_submit_button("✅ 명부 수정사항 적용")
            
            if submit:
                # [핵심] 편집기에서 넘어온 전체 데이터(추가된 행 포함)를 세션에 덮어씀
                st.session_state.df_final = convert_dates(new_edited_df)
                st.success("대시보드에 데이터가 반영되었습니다!")
                st.rerun()

# ==========================================
# [2. 메인 화면 - 대시보드]
# ==========================================
st.title("🛡️ 산업안전보건 통합 관리 시스템")

# 현재 세션 데이터 가져오기
main_df = st.session_state.df_final.copy()
active_df = main_df[main_df['퇴사여부'] == False]

# 상단 메트릭
c1, c2, c3 = st.columns(3)
c1.metric("👥 총 인원", f"{len(main_df)}명")
c2.metric("🏢 재직자", f"{len(active_df)}명")
c3.metric("🏥 검진 대상", f"{len(active_df[active_df['특수검진_대상']==True])}명")

st.divider()

# 데이터 테이블 출력
st.subheader("📋 전체 명부 현황")
st.dataframe(main_df, use_container_width=True)

if st.button("🔄 전체 화면 새로고침"):
    st.rerun()
