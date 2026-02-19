import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.set_page_config(layout="wide")

st.title("📦 치과 재고관리 시스템")

# ===============================
# 1️⃣ 엑셀 파일 목록
# ===============================

excel_files = [
    "1단계_기본골격.xlsx",
    "2단계_카테고리.xlsx",
    "3단계_유통기한.xlsx",
    "4단계_입고사용.xlsx",
    "5단계_최소재고.xlsx",
    "6단계_위치검색.xlsx",
    "7단계_대시보드.xlsx",
    "8단계_통계완성.xlsx",
]

# ===============================
# 2️⃣ 모든 엑셀 병합
# ===============================

dfs = []

for file in excel_files:
    if os.path.exists(file):
        df_temp = pd.read_excel(file)
        df_temp.columns = df_temp.columns.str.strip()
        dfs.append(df_temp)

if not dfs:
    st.error("엑셀 파일을 찾을 수 없습니다.")
    st.stop()

# 품목명 기준 병합
df = dfs[0]

for i in range(1, len(dfs)):
    df = pd.merge(
        df,
        dfs[i],
        on="품목명",
        how="outer",
        suffixes=("", f"_{i}")
    )

# ===============================
# 3️⃣ 컬럼 정리
# ===============================

def get_col(col):
    for c in df.columns:
        if c.startswith(col):
            return c
    return None

col_map = {
    "카테고리": get_col("카테고리"),
    "수량": get_col("수량"),
    "단위": get_col("단위"),
    "유통기한": get_col("유통기한"),
    "최소재고": get_col("최소재고"),
    "보관위치": get_col("보관위치"),
}

for key, value in col_map.items():
    if value:
        df[key] = df[value]
    else:
        df[key] = ""

# 수량 숫자 변환
df["수량"] = df["수량"].astype(str).str.replace(r"[^0-9]", "", regex=True)
df["수량"] = pd.to_numeric(df["수량"], errors="coerce").fillna(0).astype(int)

df["최소재고"] = pd.to_numeric(df["최소재고"], errors="coerce").fillna(0).astype(int)

# ===============================
# 4️⃣ 상태 계산
# ===============================

def calculate_status(row):
    if pd.isna(row["유통기한"]) or row["유통기한"] == "":
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

# 부족 계산
df["부족"] = df["수량"] < df["최소재고"]

# ===============================
# 5️⃣ 상단 요약
# ===============================

col1, col2, col3, col4 = st.columns(4)

col1.metric("전체 품목", len(df))
col2.metric("만료", (df["상태"] == "만료").sum())
col3.metric("임박", (df["상태"] == "임박").sum())
col4.metric("부족", df["부족"].sum())

st.divider()

# ===============================
# 6️⃣ 검색
# ===============================

search = st.text_input("🔎 검색 (품목명/위치)")

if search:
    df = df[
        df["품목명"].str.contains(search, na=False) |
        df["보관위치"].astype(str).str.contains(search, na=False)
    ]

# ===============================
# 7️⃣ 카테고리 탭
# ===============================

categories = df["카테고리"].dropna().unique().tolist()

if not categories:
    categories = ["미분류"]
    df["카테고리"] = "미분류"

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
                f"{icon} {row['품목명']} ({row['수량']} {row['단위']}) - {row['상태']}"
            ):
                st.write(f"📍 위치: {row['보관위치']}")
                st.write(f"⏳ 유통기한: {row['유통기한']}")
                st.write(f"📦 최소재고: {row['최소재고']}")
