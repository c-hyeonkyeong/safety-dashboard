import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from github import Github
import io

# --- [1. 시스템 설정] ---
st.set_page_config(page_title="GitHub 연동 대시보드", layout="wide", page_icon="🐙")
st.title("🐙 GitHub 저장소 연동 안전보건 시스템")
st.caption("데이터를 저장하면 GitHub 저장소의 'data.csv' 파일이 자동으로 업데이트됩니다.")

# --- [2. GitHub 연결 설정] ---
# Streamlit Secrets에서 토큰을 가져옵니다.
try:
    token = st.secrets["GITHUB_TOKEN"]
    g = Github(token)
    
    # 현재 리포지토리 정보를 가져오는 방법
    # (주의: 본인의 '아이디/저장소이름'을 정확히 적어야 합니다!)
    # 예: repo_name = "honggildong/safety-dashboard"
    # 지금 배포된 앱의 URL이나 GitHub 주소를 확인해서 채워주세요.
    # 만약 모르겠다면, 아래처럼 Streamlit 기능으로 추적할 수도 있지만,
    # 가장 확실한 건 직접 적는 것입니다. 아래 변수를 수정하세요!
    
    # ▼▼▼ [수정 필요] 본인의 'GitHub아이디/저장소이름'으로 바꾸세요! ▼▼▼
    REPO_KEY = "사용자ID/저장소이름" 
    # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
    
    repo = g.get_repo(REPO_KEY)
except Exception as e:
    st.error(f"GitHub 연결 실패: Secrets에 'GITHUB_TOKEN'이 설정되었는지, 리포지토리 이름이 맞는지 확인하세요.\n에러: {e}")
    st.stop()

# --- [3. 데이터 불러오기 & 저장하기 함수] ---
FILE_PATH = "data.csv"

def load_data_from_github():
    try:
        # GitHub에서 파일 내용 가져오기
        file_content = repo.get_contents(FILE_PATH)
        decoded_content = file_content.decoded_content
        # CSV 읽기
        df = pd.read_csv(io.BytesIO(decoded_content))
        # 날짜 변환
        for col in ['입사일', '최근_직무교육일', '최근_특수검진일']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        return df
    except Exception as e:
        # 파일이 없으면(처음 실행 시) None 반환
        return None

def save_data_to_github(df):
    try:
        # 데이터프레임을 CSV 문자열로 변환
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        content = csv_buffer.getvalue()

        try:
            # 파일이 이미 있으면 업데이트 (Update)
            contents = repo.get_contents(FILE_PATH)
            repo.update_file(contents.path, "Update safety data via Streamlit", content, contents.sha)
            st.toast("✅ GitHub에 저장 완료! (Update)", icon="🐙")
        except:
            # 파일이 없으면 새로 생성 (Create)
            repo.create_file(FILE_PATH, "Initial data commit", content)
            st.toast("✅ GitHub에 파일 생성 완료! (Create)", icon="🆕")
            
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")

# --- [4. 초기 데이터 로드] ---
if 'df' not in st.session_state:
    with st.spinner("GitHub에서 데이터를 불러오는 중..."):
        loaded_df = load_data_from_github()
    
    if loaded_df is not None:
        st.session_state.df = loaded_df
    else:
        # 파일이 없으면 기본 샘플 데이터 사용
        st.warning("저장된 데이터가 없어 기본 샘플을 로드합니다. [저장하기]를 누르면 파일이 생성됩니다.")
        data = {
            '성명': ['김철수', '이영희', '박신규'],
            '직책': ['안전보건관리책임자', '관리감독자', '신규채용자'],
            '부서': ['일반관리팀', '일반관리팀', '용접팀'],
            '입사일': [date(2022,1,1), date(2023,5,20), date.today()],
            '최근_직무교육일': [date(2023,5,1), date(2024,5,20), None],
            '검진단계': ['배치전(미실시)', '배치전(미실시)', '배치전(미실시)'],
            '최근_특수검진일': [None, None, None]
        }
        st.session_state.df = pd.DataFrame(data)

# --- [5. 사이드바 및 에디터] ---
# 매핑 설정
DEPT_SUBJECT_MAP = {'용접팀': '아크용접 등 화기작업', '전기팀': '고압 전기 취급 작업', '일반관리팀': '해당없음'}
DEPT_FACTOR_MAP = {'용접팀': '용접흄, 분진', '전기팀': '전류(감전)', '일반관리팀': '없음'}
DEPTS_LIST = list(DEPT_SUBJECT_MAP.keys())
ROLES = ["안전보건관리책임자", "관리감독자", "폐기물담당자", "신규채용자", "일반근로자"]
HEALTH_PHASES = ["배치전(미실시)", "1차검진 완료(다음:6개월)", "정기검진(다음:1년)"]

with st.sidebar:
    st.header("📝 데이터 관리")
    
    # 저장 버튼
    if st.button("💾 GitHub에 저장하기", use_container_width=True, type="primary"):
        save_data_to_github(st.session_state.df)
        
    st.divider()
    
    edited_df = st.data_editor(
        st.session_state.df,
        num_rows="dynamic",
        use_container_width=True,
        key="main_editor",
        column_config={
            "성명": st.column_config.TextColumn("성명", required=True),
            "직책": st.column_config.SelectboxColumn("직책", options=ROLES),
            "부서": st.column_config.SelectboxColumn("부서", options=DEPTS_LIST),
            "입사일": st.column_config.DateColumn("입사일"),
            "최근_직무교육일": st.column_config.DateColumn("최근 직무교육일"),
            "검진단계": st.column_config.SelectboxColumn("검진단계", options=HEALTH_PHASES),
            "최근_특수검진일": st.column_config.DateColumn("최근 검진일"),
        }
    )
    # 데이터 변경 즉시 반영
    if not edited_df.equals(st.session_state.df):
        st.session_state.df = edited_df
        st.rerun()

# --- [6. 로직 및 시각화] ---
df = st.session_state.df.copy()
today = date.today()

# (기존 로직 동일)
def add_days(d, days):
    if pd.isna(d) or d == "": return None
    if isinstance(d, str): d = datetime.strptime(d, "%Y-%m-%d").date() 
    return d + timedelta(days=days)

df['입사일_dt'] = pd.to_datetime(df['입사일'], errors='coerce')
df['신규자_여부'] = df.apply(lambda x: ((pd.Timestamp(today) - x['입사일_dt']).days < 90 if pd.notnull(x['입사일_dt']) else False) or (x['직책']=='신규채용자'), axis=1)
df['특별교육_과목'] = df['부서'].map(DEPT_SUBJECT_MAP).fillna("-")
df['유해인자'] = df['부서'].map(DEPT_FACTOR_MAP).fillna("-")

df['다음_직무교육일'] = None
mask_m = df['직책'] == '안전보건관리책임자'
df.loc[mask_m, '다음_직무교육일'] = df[mask_m]['최근_직무교육일'].apply(lambda x: add_days(x, 730))

st.divider()
st.info("💡 데이터를 수정하고 왼쪽 사이드바의 **[GitHub에 저장하기]** 버튼을 누르면 자동 저장됩니다.")
st.dataframe(df, use_container_width=True)
