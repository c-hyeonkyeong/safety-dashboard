# --- [1. 시스템 설정] ---
st.set_page_config(page_title="안전보건 대시보드 Pro", layout="wide", page_icon="🛡️")

# CSS로 디자인 디테일 잡기 (줄 간격 축소 및 버튼 스타일)
st.markdown("""
<style>
    div[data-testid="stMetricValue"] {font-size: 24px; font-weight: bold; color: #31333F;}
    .st-emotion-cache-16idsys p {font-size: 1rem;}
    
    /* 버튼 스타일: 높이를 줄여서 컴팩트하게 */
    div.stButton > button {
        border-radius: 6px;
        height: 32px; /* 40px -> 32px로 축소 */
        padding-top: 0px;
        padding-bottom: 0px;
        width: 100%;
    }
    
    /* 카드 박스 스타일 */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 10px;
    }

    /* 부서 설정 리스트 텍스트 수직 정렬 맞춤 */
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stMarkdownContainer"] p {
        margin-bottom: 0px; /* 텍스트 아래 여백 제거 */
        line-height: 32px;  /* 버튼 높이와 맞춰서 수직 중앙 정렬 효과 */
    }
</style>
""", unsafe_allow_html=True)
