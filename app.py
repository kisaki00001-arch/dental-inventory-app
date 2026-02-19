import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="치과 재고관리 시스템", layout="wide")

DB_NAME = "inventory.db"
EXCEL_FILE = "8단계_통계완성.xlsx"

# ---------------------------
# DB 연결
# ---------------------------
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

# ---------------------------
# 테이블 생성
# ---------------------------
cursor.execute("""
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
conn.commit()

# ---------------------------
# 최초 실행 시 엑셀 데이터 삽입
# ---------------------------
def init_from_excel():
    cursor.execute("SELECT COUNT(*) FROM inventory")
    count = cursor.fetchone()[0]

    if count == 0 and os.path.exists(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE)

        # 필수 컬럼만 사용
        required_cols = ["품목명", "카테고리", "수량", "단위", "유통기한", "최소재고", "위치"]
        df = df[required_cols]

        df["수량"] = df["수량"].fillna(0).astype(int)
        df["최소재고"] = df["최소재고"].fillna(0).astype(int)
        df["유통기한"] = df["유통기한"].astype(str)

        df.to_sql("inventory", conn, if_exists="append", index=False)
        conn.commit()

init_from_excel()

# ---------------------------
# 상태 계산 함수
# ---------------------------
def calculate_status(row):
    today = datetime.today().date()

    if row["유통기한"] and row["유통기한"] != "nan":
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

# ---------------------------
# 데이터 불러오기
# ---------------------------
df = pd.read_sql("SELECT * FROM inventory", conn)

if not df.empty:
    df["상태"] = df.apply(calculate_status, axis=1)

# ---------------------------
# 헤더
# ---------------------------
st.title("📦 치과 재고관리 시스템")

col1, col2, col3, col4 = st.columns(4)

if not df.empty:
    col1.metric("전체 품목", len(df))
    col2.metric("만료", len(df[df["상태"]=="만료"]))
    col3.metric("임박", len(df[df["상태"]=="임박"]))
    col4.metric("부족", len(df[df["상태"]=="부족"]))
else:
    col1.metric("전체 품목", 0)
    col2.metric("만료", 0)
    col3.metric("임박", 0)
    col4.metric("부족", 0)

st.divider()

# ---------------------------
# 검색
# ---------------------------
search = st.text_input("🔍 검색 (이름/카테고리/위치)")

if search:
    df = df[
        df["품목명"].str.contains(search, case=False) |
        df["카테고리"].str.contains(search, case=False) |
        df["위치"].str.contains(search, case=False)
    ]

# ---------------------------
# 카테고리 탭
# ---------------------------
categories = df["카테고리"].unique().tolist() if not df.empty else []
tabs = st.tabs(categories) if categories else []

for i, category in enumerate(categories):
    with tabs[i]:
        df_cat = df[df["카테고리"] == category]

        if df_cat.empty:
            st.info("항목 없음")
            continue

        for _, row in df_cat.iterrows():

            icon = ""
            if row["상태"] == "만료":
                icon = "🔴"
            elif row["상태"] == "임박":
                icon = "🟡"
            elif row["상태"] == "부족":
                icon = "⚠️"

            with st.expander(
                f"{icon} {row['품목명']} ({row['수량']} {row['단위']}) - {row['상태']}"
            ):
                st.write(f"📂 카테고리: {row['카테고리']}")
                st.write(f"📍 위치: {row['위치']}")
                st.write(f"⏳ 유통기한: {row['유통기한']}")
                st.write(f"📦 최소재고: {row['최소재고']}")

                # 최소재고 수정
                new_min = st.number_input(
                    "최소재고 수정",
                    min_value=0,
                    value=int(row["최소재고"]),
                    key=f"min_{row['id']}"
                )

                if st.button("저장", key=f"save_min_{row['id']}"):
                    cursor.execute(
                        "UPDATE inventory SET 최소재고=? WHERE id=?",
                        (new_min, row["id"])
                    )
                    conn.commit()
                    st.rerun()

                colA, colB = st.columns(2)

                # 입고
                with colA:
                    in_qty = st.number_input("입고 수량", min_value=1, key=f"in_{row['id']}")
                    if st.button("입고", key=f"in_btn_{row['id']}"):
                        cursor.execute(
                            "UPDATE inventory SET 수량=수량+? WHERE id=?",
                            (in_qty, row["id"])
                        )
                        conn.commit()
                        st.rerun()

                # 사용
                with colB:
                    out_qty = st.number_input("사용 수량", min_value=1, key=f"out_{row['id']}")
                    if st.button("사용", key=f"out_btn_{row['id']}"):
                        cursor.execute(
                            "UPDATE inventory SET 수량=수량-? WHERE id=?",
                            (out_qty, row["id"])
                        )
                        conn.commit()
                        st.rerun()
