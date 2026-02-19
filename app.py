import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os

st.set_page_config(layout="wide")

DB_FILE = "inventory.db"
EXCEL_FILE = "1단계_기본골격.xlsx"  # 초기데이터용

# -----------------------------
# DB 연결
# -----------------------------
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

# -----------------------------
# 테이블 생성
# -----------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    물품명 TEXT,
    카테고리 TEXT,
    수량 INTEGER,
    단위 TEXT,
    유통기한 TEXT,
    최소재고 INTEGER,
    보관위치 TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_id INTEGER,
    타입 TEXT,
    수량 INTEGER,
    날짜 TEXT,
    메모 TEXT
)
""")
conn.commit()

# -----------------------------
# 초기 엑셀 로딩 (한 번만)
# -----------------------------
def init_from_excel():
    cursor.execute("SELECT COUNT(*) FROM inventory")
    if cursor.fetchone()[0] > 0:
        return

    if not os.path.exists(EXCEL_FILE):
        return

    df = pd.read_excel(EXCEL_FILE)
    df.columns = df.columns.str.strip()

    if "물품명" not in df.columns:
        return

    for _, row in df.iterrows():
        cursor.execute("""
        INSERT INTO inventory
        (물품명, 카테고리, 수량, 단위, 유통기한, 최소재고, 보관위치)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get("물품명", ""),
            row.get("카테고리", "진료용 소모품"),
            int(row.get("수량", 0)),
            row.get("단위", ""),
            str(row.get("유통기한", "")),
            int(row.get("최소재고", 0)),
            row.get("보관위치", "")
        ))

    conn.commit()

init_from_excel()

# -----------------------------
# 상태 계산
# -----------------------------
def calculate_status(row):
    if row["수량"] <= row["최소재고"]:
        return "부족"

    if row["유통기한"]:
        try:
            exp = datetime.strptime(row["유통기한"], "%Y-%m-%d")
            if exp < datetime.today():
                return "만료"
            elif exp < datetime.today() + timedelta(days=30):
                return "임박"
        except:
            pass

    return "정상"

# -----------------------------
# 페이지 선택
# -----------------------------
page = st.sidebar.radio("메뉴", ["재고 목록", "통합 대시보드"])

# =====================================================
# 📦 재고 목록
# =====================================================
if page == "재고 목록":

    st.title("📦 치과 재고관리 시스템")

    df = pd.read_sql("SELECT * FROM inventory", conn)
    if df.empty:
        st.info("등록된 재고가 없습니다.")
        st.stop()

    df["상태"] = df.apply(calculate_status, axis=1)

    # 요약
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("전체 물품", len(df))
    col2.metric("만료", len(df[df["상태"]=="만료"]))
    col3.metric("임박", len(df[df["상태"]=="임박"]))
    col4.metric("부족", len(df[df["상태"]=="부족"]))

    st.divider()

    search = st.text_input("🔍 검색 (물품명/카테고리/위치)")
    if search:
        df = df[
            df["물품명"].str.contains(search, na=False) |
            df["카테고리"].str.contains(search, na=False) |
            df["보관위치"].str.contains(search, na=False)
        ]

    categories = ["전체","진료용 소모품","일반 비품","치과기구","치과설비"]
    selected = st.selectbox("카테고리 선택", categories)

    if selected != "전체":
        df = df[df["카테고리"] == selected]

    for _, row in df.iterrows():

        status = row["상태"]
        icon = "🟢"
        if status == "임박":
            icon = "🟡"
        elif status == "만료":
            icon = "🔴"
        elif status == "부족":
            icon = "⚠️"

        with st.expander(f"{icon} {row['물품명']} ({row['수량']} {row['단위']}) - {status}"):

            st.write("📍 위치:", row["보관위치"])
            st.write("⏳ 유통기한:", row["유통기한"])
            st.write("📦 최소재고:", row["최소재고"])

            colA, colB = st.columns(2)

            with colA:
                in_qty = st.number_input("입고 수량", 0, key=f"in{row['id']}")
                if st.button("입고", key=f"btn_in{row['id']}"):
                    cursor.execute("UPDATE inventory SET 수량=수량+? WHERE id=?",
                                   (in_qty, row["id"]))
                    cursor.execute("INSERT INTO history VALUES (NULL,?,?,?,?,?)",
                                   (row["id"], "입고", in_qty,
                                    datetime.now().strftime("%Y-%m-%d"), ""))
                    conn.commit()
                    st.rerun()

            with colB:
                out_qty = st.number_input("사용 수량", 0, key=f"out{row['id']}")
                if st.button("사용", key=f"btn_out{row['id']}"):
                    cursor.execute("UPDATE inventory SET 수량=수량-? WHERE id=?",
                                   (out_qty, row["id"]))
                    cursor.execute("INSERT INTO history VALUES (NULL,?,?,?,?,?)",
                                   (row["id"], "사용", out_qty,
                                    datetime.now().strftime("%Y-%m-%d"), ""))
                    conn.commit()
                    st.rerun()

# =====================================================
# 📊 통합 대시보드
# =====================================================
if page == "통합 대시보드":

    st.title("📊 통합 대시보드")

    df = pd.read_sql("SELECT * FROM inventory", conn)
    if df.empty:
        st.info("데이터 없음")
        st.stop()

    df["상태"] = df.apply(calculate_status, axis=1)

    col1, col2, col3 = st.columns(3)
    col1.metric("만료", len(df[df["상태"]=="만료"]))
    col2.metric("임박", len(df[df["상태"]=="임박"]))
    col3.metric("부족", len(df[df["상태"]=="부족"]))

    st.subheader("📈 카테고리별 재고 현황")

    cat_df = df.groupby("카테고리")["수량"].sum()
    fig, ax = plt.subplots()
    cat_df.plot(kind="bar", ax=ax)
    st.pyplot(fig)

    st.subheader("🔥 최근 30일 사용 TOP 5")

    history_df = pd.read_sql("SELECT * FROM history", conn)
    if not history_df.empty:
        history_df["날짜"] = pd.to_datetime(history_df["날짜"])
        last30 = history_df[
            (history_df["타입"]=="사용") &
            (history_df["날짜"] >= datetime.now()-timedelta(days=30))
        ]

        top = last30.groupby("inventory_id")["수량"].sum().sort_values(ascending=False).head(5)
        if not top.empty:
            for idx in top.index:
                name = df[df["id"]==idx]["물품명"].values[0]
                st.write(name, "-", top[idx])
