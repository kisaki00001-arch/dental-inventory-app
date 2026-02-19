import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.set_page_config(layout="wide")
st.title("📦 치과 재고관리 시스템")

# =========================
# 1️⃣ 기본 파일 읽기
# =========================

if not os.path.exists("1단계_기본골격.xlsx"):
    st.error("1단계_기본골격.xlsx 파일이 필요합니다.")
    st.stop()

df = pd.read_excel("1단계_기본골격.xlsx")
df.columns = df.columns.str.strip()

# =========================
# 2️⃣ 필수 컬럼 정리
# =========================

required_cols = ["물품명", "수량", "단위"]

for col in required_cols:
    if col not in df.columns:
        st.error(f"{col} 컬럼이 없습니다.")
        st.stop()

# 기본 컬럼 추가 (없으면 생성)

extra_cols = ["카테고리", "유통기한", "최소재고", "보관위치"]

for col in extra_cols:
    if col not in df.columns:
        df[col] = ""

# =========================
# 3️⃣ 수량 숫자 처리
# =========================

df["수량"] = df["수량"].astype(str).str.replace(r"[^0-9]", "", regex=True)
df["수량"] = pd.to_numeric(df["수량"], errors="coerce").fillna(0).astype(int)

df["최소재고"] = pd.to_numeric(df["최소재고"], errors="coerce").fillna(0).astype(int)

# =========================
# 4️⃣ 상태 계산
# =========================

def calculate_status(row):
    if not row["유통기한"]:
        return "정상"

    try:
        exp = pd.to_datetime(row["유통기한"]).date()
        today = datetime.today().date()
        diff = (exp - today).days

        if diff < 0:
            return "만료"
        elif diff <= 30:
            return "임박"
        else:
            return "정상"
    except:
        return "정상"

df["상태"] = df.apply(calculate_status, axis=1)
df["부족"] = df["수량"] < df["최소재고"]

# =========================
# 5️⃣ 대시보드
# =========================

col1, col2, col3, col4 = st.columns(4)

col1.metric("전체 물품", len(df))
col2.metric("만료", (df["상태"] == "만료").sum())
col3.metric("임박", (df["상태"] == "임박").sum())
col4.metric("부족", df["부족"].sum())

st.divider()

# =========================
# 6️⃣ 검색
# =========================

search = st.text_input("🔎 검색 (물품명/위치)")

if search:
    df = df[
        df["물품명"].str.contains(search, na=False) |
        df["보관위치"].astype(str).str.contains(search, na=False)
    ]

# =========================
# 7️⃣ 카테고리 처리
# =========================

if df["카테고리"].isnull().all() or df["카테고리"].eq("").all():
    df["카테고리"] = "미분류"

categories = df["카테고리"].unique().tolist()
tabs = st.tabs(categories)

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
            elif row["부족"]:
                icon = "⚠️"

            with st.expander(
                f"{icon} {row['물품명']} ({row['수량']} {row['단위']}) - {row['상태']}"
            ):
                st.write(f"📍 위치: {row['보관위치']}")
                st.write(f"⏳ 유통기한: {row['유통기한']}")
                st.write(f"📦 최소재고: {row['최소재고']}")
