import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

st.set_page_config(page_title="치과 재고관리 시스템", layout="wide")

DB_FILE = "inventory.db"

# ==========================
# DB 연결
# ==========================
@st.cache_resource
def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
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
    return conn

conn = get_connection()

# ==========================
# 상태 계산
# ==========================
def calculate_status(row):
    today = datetime.today().date()

    if row["유통기한"]:
        try:
            exp = datetime.strptime(row["유통기한"], "%Y-%m-%d").date()
            if exp < today:
                return "만료"
            elif exp <= today + timedelta(days=30):
                return "임박"
        except:
            pass

    if row["수량"] <= row["최소재고"]:
        return "부족"

    return "정상"

# ==========================
# 데이터 로드
# ==========================
df = pd.read_sql("SELECT * FROM inventory", conn)

if not df.empty:
    df["상태"] = df.apply(calculate_status, axis=1)
else:
    df = pd.DataFrame(columns=["품목명","카테고리","수량","단위","유통기한","최소재고","위치","상태"])

# ==========================
# 사이드바 메뉴
# ==========================
menu = st.sidebar.radio("메뉴", ["재고 목록", "대시보드"])

# ============================================================
# 📦 재고 목록 화면
# ============================================================
if menu == "재고 목록":

    st.title("📦 재고 목록")

    # 상단 통계
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("전체 품목", len(df))
    col2.metric("만료", (df["상태"]=="만료").sum())
    col3.metric("임박", (df["상태"]=="임박").sum())
    col4.metric("부족", (df["상태"]=="부족").sum())

    st.divider()

    # 검색/필터
    colA, colB, colC = st.columns(3)

    with colA:
        search = st.text_input("🔎 검색 (이름/카테고리/위치)")

    with colB:
        status_filter = st.selectbox("상태 필터", ["전체","정상","임박","만료","부족"])

    with colC:
        location_filter = st.selectbox("위치 필터", ["전체"] + sorted(df["위치"].dropna().unique().tolist()))

    # 필터 적용
    filtered_df = df.copy()

    if search:
        filtered_df = filtered_df[
            filtered_df["품목명"].str.contains(search, case=False, na=False) |
            filtered_df["카테고리"].str.contains(search, case=False, na=False) |
            filtered_df["위치"].str.contains(search, case=False, na=False)
        ]

    if status_filter != "전체":
        filtered_df = filtered_df[filtered_df["상태"] == status_filter]

    if location_filter != "전체":
        filtered_df = filtered_df[filtered_df["위치"] == location_filter]

    # 카테고리 탭
    categories = ["진료용 소모품","일반 비품","치과기구","치과설비"]
    tabs = st.tabs(categories)

    for i, category in enumerate(categories):

        with tabs[i]:

            df_cat = filtered_df[filtered_df["카테고리"] == category]

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
                    상태아이콘 = "⚠"

                with st.expander(
                    f"{상태아이콘} {row['품목명']} ({row['수량']} {row['단위']})"
                    + (" - 부족" if row["상태"]=="부족" else "")
                ):

                    st.write(f"📁 카테고리: {row['카테고리']}")
                    st.write(f"📍 위치: {row['위치']}")
                    st.write(f"⏳ 유통기한: {row['유통기한']}")
                    st.write(f"📉 최소재고: {row['최소재고']}")

                    # ================= 최소재고 수정 =================
                    edit_key = f"edit_min_{row['id']}"
                    if edit_key not in st.session_state:
                        st.session_state[edit_key] = False

                    if not st.session_state[edit_key]:
                        if st.button("✏ 최소재고 수정", key=f"btn_{row['id']}"):
                            st.session_state[edit_key] = True
                    else:
                        new_min = st.number_input(
                            "새 최소재고",
                            min_value=0,
                            value=int(row["최소재고"]),
                            key=f"input_min_{row['id']}"
                        )

                        if st.button("저장", key=f"save_{row['id']}"):
                            conn.execute(
                                "UPDATE inventory SET 최소재고=? WHERE id=?",
                                (new_min, row["id"])
                            )
                            conn.commit()
                            st.success("수정 완료")
                            st.rerun()

                    st.divider()

                    # ================= 입고/사용 =================
                    col1, col2 = st.columns(2)

                    with col1:
                        in_qty = st.number_input("입고 수량",1, key=f"in_{row['id']}")
                        if st.button("입고", key=f"inbtn_{row['id']}"):
                            conn.execute(
                                "UPDATE inventory SET 수량 = 수량 + ? WHERE id=?",
                                (in_qty, row["id"])
                            )
                            conn.commit()
                            st.rerun()

                    with col2:
                        out_qty = st.number_input("사용 수량",1, key=f"out_{row['id']}")
                        if st.button("사용", key=f"outbtn_{row['id']}"):
                            conn.execute(
                                "UPDATE inventory SET 수량 = 수량 - ? WHERE id=?",
                                (out_qty, row["id"])
                            )
                            conn.commit()
                            st.rerun()

# ============================================================
# 📊 대시보드
# ============================================================
if menu == "대시보드":

    st.title("📊 통합 대시보드")

    col1, col2, col3 = st.columns(3)

    col1.metric("만료", (df["상태"]=="만료").sum())
    col2.metric("임박", (df["상태"]=="임박").sum())
    col3.metric("부족", (df["상태"]=="부족").sum())

    st.divider()

    # 카테고리별 재고
    st.subheader("카테고리별 재고 현황")
    chart_data = df.groupby("카테고리")["수량"].sum()
    st.bar_chart(chart_data)

    # 부족 리스트
    st.subheader("주문 필요 품목")
    shortage = df[df["상태"]=="부족"]
    if not shortage.empty:
        st.dataframe(shortage[["품목명","수량","최소재고","위치"]])
    else:
        st.success("부족 품목 없음")
