import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from github import Github
import io

# --- [1. 시스템 설정] ---
st.set_page_config(page_title="안전보건 Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    div[data-testid="stMetricValue"] {font-size: 24px; font-weight: bold;}
    div.stButton > button {width: 100%; border-radius: 6px; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# [0. 초기 데이터 및 설정]
# ==========================================
EDITOR_KEY = "main_worker_editor"  # 데이터 에디터 고유 키
ROLES = ["안전보건관리책임자", "관리감독자", "폐기물담당자", "일반근로자"]
HEALTH_PHASES = ["배치전(미실시)", "1차검진 완료(다음:6개월)", "정기검진(다음:1년)"]

if 'df_final' not in st.session_state:
    st.session_state.df_final = pd.DataFrame({
        '성명': ['홍길동'], '직책': ['일반근로자'], '부서': ['일반관리팀'],
        '입사일': [pd.to_datetime('2024-01-01')], '최근_직무교육일': [pd.NaT],
        '신규교육_이수': [False], '퇴사여부': [False], '특수검진_대상': [True],
        '검진단계': ['배치전(미실시)'], '최근_특수검진일': [pd.NaT]
    })

# ==========================================
# [1. 사이드바 관리자 메뉴]
# ==========================================
with st.sidebar:
    st.header("⚙️ 관리자 설정")
    
    # --- GitHub 연동 ---
    with st.expander("☁️ GitHub 연동 (저장/불러오기)", expanded=False):
        g_token = st.text_input("🔑 토큰", type="password")
        g_repo = st.text_input("📂 레포지토리 (user/repo)")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📂 불러오기"):
                try:
                    repo = Github(g_token).get_repo(g_repo)
                    content = repo.get_contents("data.csv").decoded_content.decode("utf-8")
                    loaded_df = pd.read_csv(io.StringIO(content))
                    for col in ['입사일', '최근_직무교육일', '최근_특수검진일']:
                        if col in loaded_df.columns: loaded_df[col] = pd.to_datetime(loaded_df[col])
                    st.session_state.df_final = loaded_df
                    st.success("로드 완료!")
                    st.rerun()
                except Exception as e: st.error(f"실패: {e}")
        
        with c2:
            if st.button("💾 저장하기", type="primary"):
                try:
                    repo = Github(g_token).get_repo(g_repo)
                    df_to_save = st.session_state.df_final.copy()
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

    # --- 근로자 명부 수정 (분석 내용 반영) ---
    with st.expander("📝 근로자 명부 관리", expanded=True):
        st.info("행 추가/수정 후 반드시 '수정사항 적용'을 눌러주세요.")
        
        # 편집기에 표시할 컬럼 정의
        view_cols = ['성명', '직책', '부서', '입사일', '최근_직무교육일', '퇴사여부', '특수검진_대상', '검진단계', '최근_특수검진일']
        
        with st.form("worker_form"):
            # 분석 내용: st.data_editor의 반환값이 아닌 'key'를 통한 상태 관리가 핵심
            st.data_editor(
                st.session_state.df_final[view_cols],
                num_rows="dynamic",
                key=EDITOR_KEY,  # 이 키를 통해 session_state에서 직접 변경사항을 가져옴
                use_container_width=True,
                column_config={
                    "직책": st.column_config.SelectboxColumn(options=ROLES),
                    "검진단계": st.column_config.SelectboxColumn(options=HEALTH_PHASES),
                    "입사일": st.column_config.DateColumn(),
                    "최근_직무교육일": st.column_config.DateColumn(),
                    "최근_특수검진일": st.column_config.DateColumn()
                }
            )
            
            submit = st.form_submit_button("✅ 명부 수정사항 적용")
            
            if submit:
                # [분석 반영 해결 로직] 
                # session_state[EDITOR_KEY]에는 {edited_rows, added_rows, deleted_rows} 딕셔너리가 들어있습니다.
                state = st.session_state[EDITOR_KEY]
                df = st.session_state.df_final.copy()

                # 1. 수정된 행 반영
                for row_idx, patch in state.get("edited_rows", {}).items():
                    for col, val in patch.items():
                        df.iloc[row_idx, df.columns.get_loc(col)] = val

                # 2. 추가된 행 반영 (신규 입사자 저장 안 되는 문제 해결의 핵심)
                added_rows = state.get("added_rows", [])
                if added_rows:
                    added_df = pd.DataFrame(added_rows)
                    # 원본 컬럼 구조와 맞추기 (누락된 컬럼은 None 처리)
                    for col in df.columns:
                        if col not in added_df.columns:
                            added_df[col] = None
                    df = pd.concat([df, added_df[df.columns]], ignore_index=True)

                # 3. 삭제된 행 반영
                deleted_rows = state.get("deleted_rows", [])
                if deleted_rows:
                    df = df.drop(index=deleted_rows).reset_index(drop=True)

                # 4. 날짜 형식 보정 및 세션 저장
                for col in ['입사일', '최근_직무교육일', '최근_특수검진일']:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                
                st.session_state.df_final = df
                st.success("데이터가 반영되었습니다! 이제 '저장하기'를 눌러주세요.")
                st.rerun()

# ==========================================
# [2. 메인 화면 - 대시보드]
# ==========================================
st.title("🛡️ 산업안전보건 통합 관리 시스템")

# 업데이트된 df_final을 기반으로 대시보드 출력
main_df = st.session_state.df_final.copy()
active_df = main_df[main_df['퇴사여부'] == False]

c1, c2, c3 = st.columns(3)
c1.metric("🏢 현재 재직자", f"{len(active_df)}명")
c2.metric("🏥 특수검진 대상", f"{len(active_df[active_df['특수검진_대상']==True])}명")
c3.metric("🌱 올해 신규자", f"{len(main_df[main_df['입사일'].dt.year == datetime.now().year]) if not main_df['입사일'].isna().all() else 0}명")

st.divider()
st.subheader("📋 전체 명부 데이터 (GitHub 저장 대기 상태)")
st.dataframe(main_df, use_container_width=True)

if st.button("🔄 화면 새로고침"):
    st.rerun()
