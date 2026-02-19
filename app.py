import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

st.set_page_config(page_title="치과 재고관리 시스템", layout="wide")

# ==============================
# DB 연결
# ==============================
conn = sqlite3.connect("inventory.db", check_same_thread=False)

# ==============================
# 테이블 생성
# ==============================
conn.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    품목명 TEXT,
    카테고리 TEXT,
    수량 INTEGER,
    단위 TEXT,
    유통기한 TEXT,
    최소재고 INTEGER,
    위치 TEXT
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    품목명 TEXT,
    구분 TEXT,
    수량 INTEGER,
    날짜 TEXT
)
""")

# ==============================
# 상태 계산 함수
# ==============================
def calculate_status(row):
    today = datetime.today().date()

    # 유통기한 처리
    if row["유통기한"] and str(row["유통기한"]).strip() != "":
        try:
            exp = pd.to_datetime(row["유통기한"]).date()

            if exp < today:
                return "만료"
            elif exp <= today + timedelta(days=30):
                return "임박"

        except:
            pass  # 날짜 변환 실패해도 그냥 넘어감

    # 최소재고 부족 체크
    if row["수량"] <= row["최소재고"]:
        return "부족"

    return "정상"



# ==============================
# 메뉴
# ==============================
menu = st.sidebar.radio("메뉴", ["재고 목록", "대시보드"])


# ============================================================
# ======================== 재고 목록 ==========================
# ============================================================
if menu == "재고 목록":

    st.title("📦 재고 목록")

    df = pd.read_sql("SELECT * FROM inventory", conn)

    if df.empty:
        st.info("재고 데이터가 없습니다.")
        st.stop()

    df["상태"] = df.apply(calculate_status, axis=1)

    # 상단 KPI
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("전체 품목", len(df))
    col2.metric("만료", len(df[df["상태"] == "만료"]))
    col3.metric("임박", len(df[df["상태"] == "임박"]))
    col4.metric("부족", len(df[df["상태"] == "부족"]))

    st.divider()

    # 검색
    search = st.text_input("🔍 검색 (이름/카테고리/위치)")

    if search:
        df = df[
            df["품목명"].str.contains(search, case=False)
            | df["카테고리"].str.contains(search, case=False)
            | df["위치"].str.contains(search, case=False)
        ]

    # 상태 필터
    status_filter = st.selectbox("상태 필터", ["전체", "정상", "임박", "만료", "부족"])
    if status_filter != "전체":
        df = df[df["상태"] == status_filter]

    # 카테고리 탭
    categories = ["진료용 소모품", "일반 비품", "치과기구", "치과설비"]
    tabs = st.tabs(categories)

    for i, category in enumerate(categories):

        with tabs[i]:
            df_cat = df[df["카테고리"] == category]

            if df_cat.empty:
                st.info("해당 카테고리에 항목이 없습니다.")
                continue

            for _, row in df_cat.iterrows():

                상태아이콘 = ""
                if row["상태"] == "만료":
                    상태아이콘 = "🔴"
                elif row["상태"] == "임박":
                    상태아이콘 = "🟡"
                elif row["상태"] == "부족":
                    상태아이콘 = "⚠️"

                with st.expander(
                    f"{상태아이콘} {row['품목명']} ({row['수량']} {row['단위']}) - {row['상태']}"
                ):

                    st.write(f"📂 카테고리: {row['카테고리']}")
                    st.write(f"📍 위치: {row['위치']}")
                    st.write(f"📅 유통기한: {row['유통기한']}")
                    st.write(f"📦 최소재고: {row['최소재고']}")

                    # 최소재고 수정
                    new_min = st.number_input(
                        "최소재고 수정",
                        value=int(row["최소재고"]),
                        key=f"min_{row['id']}"
                    )
                    if st.button("최소재고 저장", key=f"save_min_{row['id']}"):
                        conn.execute(
                            "UPDATE inventory SET 최소재고=? WHERE id=?",
                            (new_min, row["id"]),
                        )
                        conn.commit()
                        st.success("최소재고 변경 완료")
                        st.rerun()

                    st.divider()

                    colA, colB = st.columns(2)

                    # 입고
                    with colA:
                        in_qty = st.number_input(
                            "입고 수량",
                            1,
                            key=f"in_{row['id']}"
                        )
                        if st.button("입고", key=f"in_btn_{row['id']}"):
                            conn.execute(
                                "UPDATE inventory SET 수량=수량+? WHERE id=?",
                                (in_qty, row["id"]),
                            )
                            conn.execute(
                                "INSERT INTO logs (품목명,구분,수량,날짜) VALUES (?,?,?,?)",
                                (row["품목명"], "입고", in_qty, datetime.now().strftime("%Y-%m-%d")),
                            )
                            conn.commit()
                            st.success("입고 완료")
                            st.rerun()

                    # 사용
                    with colB:
                        out_qty = st.number_input(
                            "사용 수량",
                            1,
                            key=f"out_{row['id']}"
                        )
                        if st.button("사용", key=f"out_btn_{row['id']}"):
                            conn.execute(
                                "UPDATE inventory SET 수량=수량-? WHERE id=?",
                                (out_qty, row["id"]),
                            )
                            conn.execute(
                                "INSERT INTO logs (품목명,구분,수량,날짜) VALUES (?,?,?,?)",
                                (row["품목명"], "사용", out_qty, datetime.now().strftime("%Y-%m-%d")),
                            )
                            conn.commit()
                            st.success("사용 완료")
                            st.rerun()


# ============================================================
# ======================== 대시보드 ==========================
# ============================================================
elif menu == "대시보드":

    st.title("📊 통합 대시보드")

    df = pd.read_sql("SELECT * FROM inventory", conn)
    logs = pd.read_sql("SELECT * FROM logs", conn)

    if df.empty:
        st.info("재고 데이터가 없습니다.")
        st.stop()

    df["상태"] = df.apply(calculate_status, axis=1)

    col1, col2, col3 = st.columns(3)
    col1.metric("만료", len(df[df["상태"] == "만료"]))
    col2.metric("임박", len(df[df["상태"] == "임박"]))
    col3.metric("부족", len(df[df["상태"] == "부족"]))

    st.divider()

    # 최근 30일 사용 TOP 5
    if not logs.empty:
        logs["날짜"] = pd.to_datetime(logs["날짜"])
        recent = logs[
            (logs["구분"] == "사용")
            & (logs["날짜"] >= datetime.today() - timedelta(days=30))
        ]

        top5 = (
            recent.groupby("품목명")["수량"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )

        st.subheader("최근 30일 사용 TOP5")
        st.bar_chart(top5)

    st.divider()

    st.subheader("카테고리별 재고 현황")
    cat_chart = df.groupby("카테고리")["수량"].sum()
    st.bar_chart(cat_chart)
