import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="치과 재고관리 시스템", layout="wide")

DB_FILE = "inventory.db"

# ==========================
# DB 연결
# ==========================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

# ==========================
# 테이블 생성
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    카테고리 TEXT,
    물품명 TEXT,
    수량 INTEGER,
    단위 TEXT,
    유통기한 TEXT,
    최소재고 INTEGER,
    위치 TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    물품명 TEXT,
    날짜 TEXT,
    구분 TEXT,
    수량 INTEGER,
    메모 TEXT
)
""")

conn.commit()

# ==========================
# 초기 엑셀 데이터 로드 (처음 실행 시)
# ==========================
def initialize_from_excel():
    if cursor.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
        try:
            df = pd.read_excel("8단계_통계완성.xlsx")
            df.fillna("", inplace=True)

            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT INTO inventory
                    (카테고리, 물품명, 수량, 단위, 유통기한, 최소재고, 위치)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get("카테고리", ""),
                    row.get("물품명", ""),
                    int(row.get("수량", 0)),
                    row.get("단위", ""),
                    str(row.get("유통기한", "")),
                    int(row.get("최소재고", 0)),
                    row.get("위치", "")
                ))
            conn.commit()
        except:
            pass

initialize_from_excel()

# ==========================
# 유통기한 상태 계산
# ==========================
def expiry_status(date_str):
    if not date_str or date_str == "":
        return "없음"
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        today = datetime.today()
        if today > d:
            return "만료"
        elif (d - today).days <= 30:
            return "임박"
        else:
            return "정상"
    except:
        return "없음"

# ==========================
# 사이드 메뉴
# ==========================
menu = st.sidebar.radio("메뉴", [
    "재고 목록",
    "대시보드"
])

# ===================================================
# 재고 목록
# ===================================================
if menu == "재고 목록":

    st.title("📦 재고 목록")

    search = st.text_input("🔍 검색 (이름/카테고리/위치)")

    df = pd.read_sql("SELECT * FROM inventory", conn)

    if search:
        df = df[
            df["물품명"].str.contains(search, case=False) |
            df["카테고리"].str.contains(search, case=False) |
            df["위치"].str.contains(search, case=False)
        ]

    for idx, row in df.iterrows():

        status = expiry_status(row["유통기한"])
        부족 = row["수량"] <= row["최소재고"]

        color = ""
        if status == "만료":
            color = "🔴"
        elif status == "임박":
            color = "🟡"

        부족표시 = "⚠️ 부족" if 부족 else ""

        with st.expander(f"{color} {row['물품명']} ({row['수량']} {row['단위']}) {부족표시}"):

            st.write(f"카테고리: {row['카테고리']}")
            st.write(f"위치: {row['위치']}")
            st.write(f"유통기한: {row['유통기한']}")
            st.write(f"최소재고: {row['최소재고']}")

            col1, col2 = st.columns(2)

            with col1:
                in_qty = st.number_input("입고 수량", min_value=1, key=f"in{idx}")
                if st.button("입고", key=f"inbtn{idx}"):
                    cursor.execute("UPDATE inventory SET 수량 = 수량 + ? WHERE id = ?",
                                   (in_qty, row["id"]))
                    cursor.execute("""
                        INSERT INTO transactions (물품명, 날짜, 구분, 수량, 메모)
                        VALUES (?, ?, '입고', ?, '')
                    """, (row["물품명"], datetime.now(), in_qty))
                    conn.commit()
                    st.success("입고 완료")
                    st.rerun()

            with col2:
                out_qty = st.number_input("사용 수량", min_value=1, key=f"out{idx}")
                if st.button("사용", key=f"outbtn{idx}"):
                    cursor.execute("UPDATE inventory SET 수량 = 수량 - ? WHERE id = ?",
                                   (out_qty, row["id"]))
                    cursor.execute("""
                        INSERT INTO transactions (물품명, 날짜, 구분, 수량, 메모)
                        VALUES (?, ?, '사용', ?, '')
                    """, (row["물품명"], datetime.now(), out_qty))
                    conn.commit()
                    st.success("사용 완료")
                    st.rerun()

# ===================================================
# 대시보드
# ===================================================
if menu == "대시보드":

    st.title("📊 통합 대시보드")

    df = pd.read_sql("SELECT * FROM inventory", conn)
    trans = pd.read_sql("SELECT * FROM transactions", conn)

    today = datetime.today()

    만료 = sum(expiry_status(x) == "만료" for x in df["유통기한"])
    임박 = sum(expiry_status(x) == "임박" for x in df["유통기한"])
    부족 = sum(df["수량"] <= df["최소재고"])

    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 만료", 만료)
    col2.metric("🟡 임박", 임박)
    col3.metric("⚠️ 부족", 부족)

    st.divider()

    st.subheader("최근 30일 사용 TOP 5")

    if not trans.empty:
        trans["날짜"] = pd.to_datetime(trans["날짜"])
        recent = trans[
            (trans["구분"] == "사용") &
            (trans["날짜"] >= today - timedelta(days=30))
        ]
        top5 = recent.groupby("물품명")["수량"].sum().sort_values(ascending=False).head(5)
        st.bar_chart(top5)
