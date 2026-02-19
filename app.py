import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta

st.set_page_config(layout="wide")

DB_FILE = "inventory.db"
EXCEL_FILE = "1단계_기본골격.xlsx"

# =========================
# DB 연결
# =========================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    품목명 TEXT,
    카테고리 TEXT,
    수량 INTEGER,
    단위 TEXT,
    유통기한 TEXT,
    최소재고 INTEGER,
    위치 TEXT,
    상태 TEXT
)
""")
conn.commit()


# =========================
# 상태 계산
# =========================
def calculate_status(row):
    today = datetime.today().date()

    qty = row["수량"]
    min_qty = row["최소재고"]

    # 기본 상태
    status = "정상"

    # 부족 체크
    if qty <= min_qty:
        status = "부족"

    # 유통기한 체크
    if row["유통기한"]:
        try:
            exp = datetime.strptime(row["유통기한"], "%Y-%m-%d").date()
            if exp < today:
                status = "만료"
            elif exp <= today + timedelta(days=30):
                status = "임박"
        except:
            pass

    return status


# =========================
# 엑셀 초기 데이터 로딩
# =========================
def init_from_excel():
    cursor.execute("SELECT COUNT(*) FROM inventory")
    count = cursor.fetchone()[0]
    if count > 0:
        return

    if not os.path.exists(EXCEL_FILE):
        return

    df = pd.read_excel(EXCEL_FILE)
    df.columns = df.columns.str.strip()

    # 컬럼 자동 대응
    df["품목명"] = df.get("품목명", df.get("물품명", ""))
    df["카테고리"] = df.get("카테고리", "")
    df["단위"] = df.get("단위", "개")
    df["최소재고"] = df.get("최소재고", 0)

    # 위치
    if "보관위치" in df.columns:
        df["위치"] = df["보관위치"]
    else:
        df["위치"] = ""

    # 수량 정리 (2개, 3박스 → 숫자만)
    df["수량"] = df["수량"].astype(str).str.replace(r"[^0-9]", "", regex=True)
    df["수량"] = pd.to_numeric(df["수량"], errors="coerce").fillna(0).astype(int)

    # 유통기한 정리
    if "유통기한" in df.columns:
        df["유통기한"] = pd.to_datetime(df["유통기한"], errors="coerce").dt.strftime("%Y-%m-%d")
    else:
        df["유통기한"] = ""

    df["최소재고"] = pd.to_numeric(df["최소재고"], errors="coerce").fillna(0).astype(int)

    df["상태"] = df.apply(calculate_status, axis=1)

    df = df[["품목명","카테고리","수량","단위","유통기한","최소재고","위치","상태"]]

    df.to_sql("inventory", conn, if_exists="append", index=False)
    conn.commit()


init_from_excel()


# =========================
# 데이터 불러오기
# =========================
df = pd.read_sql("SELECT * FROM inventory", conn)


# =========================
# 상단 대시보드
# =========================
total = len(df)
expired = len(df[df["상태"] == "만료"])
urgent = len(df[df["상태"] == "임박"])
shortage = len(df[df["상태"] == "부족"])

st.title("📦 치과 재고관리 시스템")

col1, col2, col3, col4 = st.columns(4)
col1.metric("전체 품목", total)
col2.metric("만료", expired)
col3.metric("임박", urgent)
col4.metric("부족", shortage)

st.divider()

# =========================
# 검색
# =========================
search = st.text_input("🔍 검색 (품목명/위치)")

if search:
    df = df[df["품목명"].str.contains(search, na=False) | df["위치"].str.contains(search, na=False)]

# =========================
# 카테고리 탭
# =========================
categories = df["카테고리"].dropna().unique().tolist()

if not categories:
    st.info("카테고리가 없습니다.")
else:
    tabs = st.tabs(categories)

    for i, category in enumerate(categories):
        with tabs[i]:

            df_cat = df[df["카테고리"] == category]

            if df_cat.empty:
                st.info("해당 카테고리에 항목이 없습니다.")
                continue

            for _, row in df_cat.iterrows():

                icon = ""
                if row["상태"] == "만료":
                    icon = "🔴"
                elif row["상태"] == "임박":
                    icon = "🟡"
                elif row["상태"] == "부족":
                    icon = "⚠️"

                with st.expander(f"{icon} {row['품목명']} ({row['수량']} {row['단위']}) - {row['상태']}"):

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

                    if st.button("최소재고 저장", key=f"save_{row['id']}"):
                        cursor.execute(
                            "UPDATE inventory SET 최소재고=? WHERE id=?",
                            (new_min, row["id"])
                        )
                        conn.commit()
                        st.rerun()

                    colA, colB = st.columns(2)

                    with colA:
                        in_qty = st.number_input("입고 수량", min_value=1, key=f"in_{row['id']}")
                        if st.button("입고", key=f"inbtn_{row['id']}"):
                            cursor.execute(
                                "UPDATE inventory SET 수량=수량+? WHERE id=?",
                                (in_qty, row["id"])
                            )
                            conn.commit()
                            st.rerun()

                    with colB:
                        out_qty = st.number_input("사용 수량", min_value=1, key=f"out_{row['id']}")
                        if st.button("사용", key=f"outbtn_{row['id']}"):
                            cursor.execute(
                                "UPDATE inventory SET 수량=수량-? WHERE id=?",
                                (out_qty, row["id"])
                            )
                            conn.commit()
                            st.rerun()
