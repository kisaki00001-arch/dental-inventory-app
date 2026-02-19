import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, date

DB_FILE = "inventory.db"
EXCEL_FILE = "1단계_기본골격.xlsx"

# ---------------- DB 연결 ----------------
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    물품명 TEXT,
    카테고리 TEXT,
    수량 INTEGER,
    단위 TEXT,
    유통기한 TEXT,
    상태 TEXT,
    최소재고 INTEGER,
    위치 TEXT
)
""")
conn.commit()


# ---------------- 엑셀 초기 로딩 ----------------
def init_from_excel():
    cursor.execute("SELECT COUNT(*) FROM inventory")
    count = cursor.fetchone()[0]
    if count > 0:
        return

    if not os.path.exists(EXCEL_FILE):
        return

    df = pd.read_excel(EXCEL_FILE)
    df.columns = df.columns.str.strip()

    if "보관위치" in df.columns:
        df["위치"] = df["보관위치"]
    else:
        df["위치"] = ""

    df["수량"] = df["수량"].astype(str).str.replace(r"[^0-9]", "", regex=True)
    df["수량"] = pd.to_numeric(df["수량"], errors="coerce").fillna(0).astype(int)

    if "최소재고" not in df.columns:
        df["최소재고"] = 0

    for _, row in df.iterrows():
        cursor.execute("""
        INSERT INTO inventory
        (물품명, 카테고리, 수량, 단위, 유통기한, 상태, 최소재고, 위치)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get("물품명",""),
            row.get("카테고리",""),
            row.get("수량",0),
            row.get("단위",""),
            str(row.get("유통기한","")),
            row.get("상태","정상"),
            row.get("최소재고",0),
            row.get("위치","")
        ))

    conn.commit()


init_from_excel()


# ---------------- 상태 계산 ----------------
def calculate_status(row):
    try:
        exp = datetime.strptime(str(row["유통기한"]), "%Y-%m-%d").date()
        if exp < date.today():
            return "만료"
        elif (exp - date.today()).days <= 30:
            return "임박"
    except:
        pass

    if row["수량"] <= row["최소재고"]:
        return "부족"

    return "정상"


# ---------------- UI ----------------
st.title("📦 치과 재고관리 시스템")

df = pd.read_sql("SELECT * FROM inventory", conn)

if not df.empty:
    df["상태"] = df.apply(calculate_status, axis=1)

total = len(df)
expired = len(df[df["상태"]=="만료"])
imminent = len(df[df["상태"]=="임박"])
low = len(df[df["상태"]=="부족"])

col1, col2, col3, col4 = st.columns(4)
col1.metric("전체 품목", total)
col2.metric("만료", expired)
col3.metric("임박", imminent)
col4.metric("부족", low)

st.divider()

categories = df["카테고리"].unique().tolist()
tabs = st.tabs(categories)

for i, category in enumerate(categories):
    with tabs[i]:

        df_cat = df[df["카테고리"] == category]

        for _, row in df_cat.iterrows():

            if row["상태"] == "만료":
                icon = "🔴"
            elif row["상태"] == "임박":
                icon = "🟡"
            elif row["상태"] == "부족":
                icon = "⚠️"
            else:
                icon = "🟢"

            with st.expander(f"{icon} {row['물품명']} ({row['수량']} {row['단위']}) - {row['상태']}"):

                st.write(f"📍 위치: {row['위치']}")
                st.write(f"⏳ 유통기한: {row['유통기한']}")
                st.write(f"📦 최소재고: {row['최소재고']}")

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
