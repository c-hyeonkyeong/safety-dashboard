import streamlit as st
import pandas as pd
import datetime as dt
from datetime import timedelta

# ---------------------------------------------------------
# [설정] 페이지 및 스타일
# ---------------------------------------------------------
st.set_page_config(page_title="안전보건 대시보드", layout="wide", page_icon="🛡️")
st.markdown("""
<style>
    div[data-testid="stMetricValue"] {font-size: 24px; font-weight: bold; color: #31333F;}
    .stButton > button {width: 100%; border-radius: 6px;}
</style>
""", unsafe_allow_html=True)

st.title("🛡️ 안전보건 대시보드 (통합)")

# ==========================================
# 0. 공통 함수 및 설정
# ==========================================
# 특별교육 허용 옵션
SPECIAL_EDU_VALID_OPTIONS = [
    "4. 폭발성·물반응성·자기반응성·자기발열성 물질, 자연발화성 액체·고체 및 인화성 액체의 제조 또는 취급작업",
    "35. 허가 및 관리 대상 유해물질의 제조 또는 취급작업"
]

def add_days(d, days):
    """날짜 더하기 유틸리티 함수"""
    try:
        if pd.isna(d) or str(d).strip() == "" or str(d) == "NaT": return None
        return pd.to_datetime(d).date() + timedelta(days=days)
    except: return None

# ---------------------------------------------------------
# 1. 데이터 로드 (파일 업로드 OR 샘플 데이터)
# ---------------------------------------------------------
st.header("1. 데이터 불러오기")

with st.expander("📂 파일 업로드 (클릭)", expanded=True):
    col1, col2 = st.columns(2)
    data_file = col1.file_uploader("기본 데이터 (사번, 성명, 입사일, 직책...)", type=["xlsx", "csv"])
    dept_file = col2.file_uploader("부서 설정 (사번, 부서명, 유해인자...)", type=["xlsx", "csv"])

# [편의기능] 파일 없을 때 테스트용 샘플 데이터 생성
if "df_data" not in st.session_state:
    st.session_state.df_data = None
if "df_dept" not in st.session_state:
    st.session_state.df_dept = None

if st.button("🧪 파일 없이 샘플 데이터로 테스트하기"):
    # 샘플 기본 데이터
    sample_data = {
        '사번': ['A001', 'A002', 'A003', 'A004', 'A005'],
        '성명': ['김철수', '이영희', '박신규', '최신규', '강폐기'],
        '입사일': ['2022-01-01', '2023-05-20', '2025-01-10', '2024-11-01', '2020-03-01'],
        '직책': ['안전보건관리책임자', '관리감독자', '일반근로자', '일반근로자', '폐기물담당자'],
        '최근_직무교육일': ['2023-05-01', '2024-05-20', None, None, '2022-04-01'],
        '최근_특수검진일': [None, None, None, None, '2023-01-01'],
        '대상 여부': ['Y', 'Y', 'Y', 'N', 'Y'],  # 특수검진 대상 여부
        '특별교육_이수여부': ['해당없음', '해당없음', '해당없음', '해당없음', '4. 폭발성...']
    }
    # 샘플 부서 데이터
    sample_dept = {
        '사번': ['A001', 'A002', 'A003', 'A004', 'A005'],
        '부서명': ['관리팀', '생산팀', '용접팀', '용접팀', '환경팀'],
        '특별교육과목': ['해당없음', '해당없음', '4. 폭발성·물반응성·자기반응성·자기발열성 물질, 자연발화성 액체·고체 및 인화성 액체의 제조 또는 취급작업', '해당없음', '35. 허가 및 관리 대상 유해물질의 제조 또는 취급작업']
    }
    st.session_state.df_data = pd.DataFrame(sample_data)
    st.session_state.df_dept = pd.DataFrame(sample_dept)
    st.toast("샘플 데이터가 로드되었습니다!", icon="✅")

# 파일 업로드 시 데이터 로드
if data_file: 
    st.session_state.df_data = pd.read_excel(data_file) if data_file.name.endswith('.xlsx') else pd.read_csv(data_file)
if dept_file: 
    st.session_state.df_dept = pd.read_excel(dept_file) if dept_file.name.endswith('.xlsx') else pd.read_csv(dept_file)

# ---------------------------------------------------------
# 2. 데이터 병합 및 가공
# ---------------------------------------------------------
if st.session_state.df_data is not None and st.session_state.df_dept is not None:
    df_data = st.session_state.df_data
    df_dept = st.session_state.df_dept

    try:
        # 2-1. 병합
        merged_df = pd.merge(df_data, df_dept, on="사번", how="left")
        
        # 2-2. 날짜 변환 및 입사년도 생성
        date_cols = ['입사일', '최근_직무교육일', '최근_특수검진일']
        for col in date_cols:
            if col in merged_df.columns:
                merged_df[col] = pd.to_datetime(merged_df[col], errors='coerce').dt.date

        merged_df['입사년도'] = pd.to_datetime(merged_df['입사일']).dt.year

        # ---------------------------------------------------------
        # [요청 반영 1] 폐기물 담당자 다음 예정일 자동 계산 (3년)
        # ---------------------------------------------------------
        merged_df['다음_직무교육일'] = None
        
        # 책임자/관리감독자 계산
        merged_df.loc[merged_df['직책']=='안전보건관리책임자', '다음_직무교육일'] = merged_df['최근_직무교육일'].apply(lambda x: add_days(x, 730))
        merged_df.loc[merged_df['직책']=='관리감독자', '다음_직무교육일'] = merged_df['최근_직무교육일'].apply(lambda x: add_days(x, 365))
        
        # 폐기물 담당자 (3년 = 1095일)
        mask_waste = merged_df['직책'].astype(str).str.strip() == '폐기물담당자'
        merged_df.loc[mask_waste, '다음_직무교육일'] = merged_df.loc[mask_waste, '최근_직무교육일'].apply(lambda x: add_days(x, 1095))

        # ---------------------------------------------------------
        # [요청 반영 4] 특별교육 목록 필터링 (4번, 35번만 허용)
        # ---------------------------------------------------------
        if '특별교육과목' in merged_df.columns:
            merged_df['특별교육과목'] = merged_df['특별교육과목'].apply(
                lambda x: x if any(opt in str(x) for opt in ["4.", "35."]) else "해당없음"
            )

        st.success("데이터 병합 및 계산 완료!")

    except Exception as e:
        st.error(f"데이터 처리 중 오류 발생: {e}")
        st.stop()

    # ---------------------------------------------------------
    # 3. 대시보드 탭 구성
    # ---------------------------------------------------------
    tab1, tab2, tab3 = st.tabs(["📊 신규 입사자 조회", "🏥 특수건강검진", "♻️ 직무/특별 교육"])

    # --- [탭 1] 신규 입사자 3개년 조회 ---
    with tab1:
        st.subheader("신규 입사자 조회 (최근 3개년)")
        
        current_year = dt.date.today().year
        recent_years = [current_year, current_year - 1, current_year - 2]
        
        # [요청 반영 2] 3개년 선택 멀티셀렉트
        selected_years = st.multiselect(
            "조회할 입사년도 선택",
            options=recent_years,
            default=recent_years
        )
        
        filtered_new = merged_df[merged_df['입사년도'].isin(selected_years)].copy()
        st.dataframe(filtered_new[['사번', '성명', '부서명', '입사일', '입사년도']], use_container_width=True)
        st.caption(f"총 {len(filtered_new)}명 조회됨")

    # --- [탭 2] 특수건강검진 ---
    with tab2:
        st.subheader("특수건강검진 관리")
        
        # [요청 반영 3] 미대상자(N) 제외 기능
        exclude_non_target = st.checkbox("대상자 아님(N) 제외하고 보기", value=True)
        
        filtered_health = merged_df.copy()
        if exclude_non_target and '대상 여부' in filtered_health.columns:
            filtered_health = filtered_health[filtered_health['대상 여부'] == 'Y']
            
        st.dataframe(filtered_health[['사번', '성명', '부서명', '대상 여부', '최근_특수검진일']], use_container_width=True)

    # --- [탭 3] 교육 관리 (폐기물/특별) ---
    with tab3:
        st.subheader("직무 및 특별 교육 관리")
        
        # 폐기물 담당자 확인
        waste_df = merged_df[merged_df['직책'] == '폐기물담당자'].copy()
        if not waste_df.empty:
            st.markdown("##### ♻️ 폐기물 담당자 (3년 주기)")
            st.dataframe(waste_df[['성명', '부서명', '최근_직무교육일', '다음_직무교육일']], use_container_width=True)
        
        # 특별교육 대상자 확인 (4번, 35번만)
        st.divider()
        st.markdown("##### ⚠️ 특별교육 대상자 (4번, 35번)")
        special_df = merged_df[merged_df['특별교육과목'].astype(str).str.contains("4\.|35\.", regex=True)].copy()
        if not special_df.empty:
            st.dataframe(special_df[['성명', '부서명', '특별교육과목']], use_container_width=True)
        else:
            st.info("해당하는 특별교육 대상자가 없습니다.")

else:
    st.info("👆 위 버튼을 눌러 샘플 데이터로 테스트하거나, 엑셀 파일을 업로드해주세요.")
