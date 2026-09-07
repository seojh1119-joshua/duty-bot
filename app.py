# ---------------------------------------------------------
# TAB 4: 월별 근무 통계 (그래프 범위 제한 및 근무시간 산출표)
# ---------------------------------------------------------
with tab3:
    st.subheader("📊 숙직근무자 월별 근무 통계")
    st.caption("📌 **근무 시간 산출 기준:** 금요일 15시간, 토요일 15시간, 일요일 7시간, 평일 7시간 | **휴일근무 횟수:** 토요일 + 일요일 근무 횟수")

    duty_stat_df = st.session_state.df.copy()

    available_stat_months = ["전체 기간"] + sorted(duty_stat_df["년월"].dropna().unique(), reverse=True)
    curr_ym = today.strftime("%Y-%m")
    default_stat_idx = available_stat_months.index(curr_ym) if curr_ym in available_stat_months else 0

    col_s1, _ = st.columns([1, 2])
    with col_s1:
        selected_stat_month = st.selectbox(
            "📅 통계 조회 월 선택",
            available_stat_months,
            index=default_stat_idx,
            key="stat_month_select"
        )

    filtered_df = duty_stat_df.copy() if selected_stat_month == "전체 기간" else duty_stat_df[duty_stat_df["년월"] == selected_stat_month].copy()

    # 근무자1, 근무자2 데이터 결합
    w1 = filtered_df[["실제근무1", "근무구분_원본"]].rename(columns={"실제근무1": "근무자", "근무구분_원본": "근무구분"})
    w2 = filtered_df[["실제근무2", "근무구분_원본"]].rename(columns={"실제근무2": "근무자", "근무구분_원본": "근무구분"})
    
    combined = pd.concat([w1, w2], ignore_index=True)
    combined["근무자"] = combined["근무자"].astype(str).str.strip()
    combined["근무구분"] = combined["근무구분"].astype(str).str.strip()
    
    # 예외/미지정 근무자 제외
    combined = combined[
        combined["근무자"].notnull() & 
        (~combined["근무자"].isin(["미지정", "nan", "None", "", "NaN"])) &
        (~combined["근무구분"].isin(["nan", "None", "", "NaN"]))
    ]

    if not combined.empty:
        # 피벗 테이블 생성
        stats_df = pd.crosstab(index=combined["근무자"], columns=combined["근무구분"], margins=False)
        
        # 1. 휴일근무 횟수 계산 (토요일 + 일요일)
        sat_cnt = stats_df["토요일"] if "토요일" in stats_df.columns else 0
        sun_cnt = stats_df["일요일"] if "일요일" in stats_df.columns else 0
        stats_df["휴일근무 횟수"] = sat_cnt + sun_cnt

        # 2. 근무시간 계산 (금: 15h, 토: 15h, 일: 7h, 평일/기타: 7h)
        hours_per_type = {
            "금요일": 15,
            "토요일": 15,
            "일요일": 7,
            "평일": 7
        }

        total_hours = pd.Series(0, index=stats_df.index)
        for col in stats_df.columns:
            if col in hours_per_type:
                total_hours += stats_df[col] * hours_per_type[col]
            elif col not in ["총 근무 횟수", "휴일근무 횟수"]:
                total_hours += stats_df[col] * 7

        stats_df["총 근무시간(h)"] = total_hours

        # 3. 총 근무 횟수 연산
        type_cols = [c for c in stats_df.columns if c not in ["총 근무 횟수", "휴일근무 횟수", "총 근무시간(h)"]]
        stats_df["총 근무 횟수"] = stats_df[type_cols].sum(axis=1)

        # 열 정렬 및 근무시간 내림차순 정렬
        ordered_cols = type_cols + ["휴일근무 횟수", "총 근무 횟수", "총 근무시간(h)"]
        stats_df = stats_df[ordered_cols].sort_values(by="총 근무시간(h)", ascending=False)

        # 요약 메트릭
        m1, m2, m3 = st.columns(3)
        m1.metric("총 근무 인원", f"{len(stats_df)}명")
        m2.metric("총 근무건수 합계", f"{int(stats_df['총 근무 횟수'].sum())}건")
        m3.metric("총 근무시간 합계", f"{int(stats_df['총 근무시간(h)'].sum())}시간")

        st.markdown("---")

        # ---------------------------------------------------------
        # 1. 그래프 범위 제한 기능
        # ---------------------------------------------------------
        st.markdown(f"#### 📊 [{selected_stat_month}] 근무자별 총 근무시간 비교 차트")
        
        max_workers = len(stats_df)
        default_limit = min(10, max_workers)
        
        top_n = st.slider(
            "차트에 표시할 상위 근무자 수 제한", 
            min_value=1, 
            max_value=max_workers, 
            value=default_limit,
            help="근무시간이 많은 상위 N명의 근무자만 차트에 표시합니다."
        )
        
        # 상위 N명 데이터만 추출하여 그래프 출력
        chart_df = stats_df.head(top_n)[["총 근무시간(h)"]]
        st.bar_chart(chart_df)

        st.markdown("---")

        # ---------------------------------------------------------
        # 2. 상세 근무시간 산출표 (합계 Row 포함)
        # ---------------------------------------------------------
        st.markdown(f"#### 📋 [{selected_stat_month}] 근무시간 산출 상세 집계표")
        
        display_df = stats_df.copy()
        
        # 합계(Total) 행 추가
        total_row = display_df.sum(axis=0)
        total_row.name = "합계"
        display_df = pd.concat([display_df, pd.DataFrame(total_row).T])

        st.dataframe(display_df, use_container_width=True, height=500)

    else:
        st.info("조회할 근무 정보가 존재하지 않습니다.")
