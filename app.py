# 컨테이너로 감싸서 깔끔하게
    with st.container(border=True):
        for i, row in df_config.iterrows():
            # gap="small"로 좌우 간격도 좁힘, 수직 정렬 center
            c1, c2, c3 = st.columns([8, 1, 1], gap="small", vertical_alignment="center")
            
            with c1:
                # 텍스트 출력
                st.markdown(f"**{i+1}. {row['부서명']}**")
            
            with c2:
                if i > 0: # 맨 위가 아니면 위로 버튼
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
                if i < len(df_config) - 1: # 맨 아래가 아니면 아래로 버튼
                    if st.button("⬇️", key=f"down_{i}", help="아래로 이동"):
                        curr_idx = df_config.at[i, '정렬순서']
                        next_idx = df_config.at[i+1, '정렬순서']
                        mask_curr = st.session_state.dept_config['정렬순서'] == curr_idx
                        mask_next = st.session_state.dept_config['정렬순서'] == next_idx
                        st.session_state.dept_config.loc[mask_curr, '정렬순서'] = 9999
                        st.session_state.dept_config.loc[mask_next, '정렬순서'] = curr_idx
                        st.session_state.dept_config.loc[mask_curr, '정렬순서'] = next_idx
                        st.rerun()
            
            # [핵심 수정] 줄 간격이 좁은 커스텀 구분선 (기본 --- 대신 사용)
            if i < len(df_config) - 1:
                st.markdown('<hr style="margin: 5px 0; border-top: 1px solid #e0e0e0;">', unsafe_allow_html=True)
