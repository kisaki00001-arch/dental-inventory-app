import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

st.set_page_config(layout="wide")
DB = "inventory.db"

conn = sqlite3.connect(DB, check_same_thread=False)
cursor = conn.cursor()

# ==========================
# 테이블 생성
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    물품명 TEXT UNIQUE,
    카테고리 TEXT,
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
    날짜 TEXT,
    물품명 TEXT,
    구분 TEXT,
    수량 INTEGER,
    메모 TEXT
)
""")
conn.commit()

# ==========================
# 엑셀 통합 초기 세팅
# ==========================
def initialize():
    if cursor.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] > 0:
        return

    base = pd.read_excel("1단계_기본골격.xlsx")
    cat = pd.read_excel("2단계_카테고리.xlsx")
    expiry = pd.read_excel("3단계_유통기한.xlsx")
    min_stock = pd.read_excel("5단계_최소재고.xlsx")
    location = pd.read_excel("6단계_위치검색.xlsx")

    df = base.merge(cat, on="물품명", how="left")
    df = df.merge(expiry, on="물품명", how="left")
    df = df.merge(min_stock, on="물품명", how="left")
    df = df.merge(location, on="물품명", how="left")

    df.fillna("", inplace=True)

    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO inventory
            (물품명, 카테고리, 수량, 단위, 유통기한, 최소재고, 위치)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row["물품명"],
            row.get("카테고리", ""),
            int(row.get("수량", 0)),
            row.get("단위", ""),
            str(row.get("유통기한", "")),
            int(row.get("최소재고", 0)),
            row.get("위치", "")
        ))
    conn.commit()

initialize()

# ==========================
# 유통기한 상태 계산
# ==========================
def expiry_status(date_str):
    if not date_str:
        return "없음"
    try:
        d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
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
# 메뉴
# ==========================
menu = st.sidebar.radio("메뉴", ["재고 목록", "대시보드"])

# ==========================
# 재고 목록
# ==========================
if menu == "재고 목록":

    st.title("📦 재고 목록")

    # ==========================
    # 전체 데이터 로드
    # ==========================
    df = pd.read_sql("SELECT * FROM inventory", conn)

    # ==========================
    # 상단 요약 카드
    # ==========================
    inv_all = df.copy()

    만료 = sum(expiry_status(x) == "만료" for x in inv_all["유통기한"])
    임박 = sum(expiry_status(x) == "임박" for x in inv_all["유통기한"])
    부족 = sum(inv_all["수량"] <= inv_all["최소재고"])
    전체 = len(inv_all)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 전체 품목", 전체)
    col2.metric("🔴 만료", 만료)
    col3.metric("🟡 임박", 임박)
    col4.metric("⚠️ 부족", 부족)

    st.divider()

    # ==========================
    # 필터 영역
    # ==========================
    col1, col2, col3 = st.columns(3)

    search = col1.text_input("🔍 검색 (이름/카테고리/위치)")
    status_filter = col2.selectbox(
        "상태 필터",
        ["전체", "정상", "임박", "만료", "부족"]
    )
    location_filter = col3.selectbox(
        "위치 필터",
        ["전체"] + sorted(df["위치"].unique().tolist())
    )

    # ==========================
    # 상태 계산
    # ==========================
    def get_status(row):
        status = expiry_status(row["유통기한"])
        부족 = row["수량"] <= row["최소재고"]
        if 부족:
            return "부족"
        return status

    df["상태"] = df.apply(get_status, axis=1)

    # ==========================
    # 필터 적용
    # ==========================
    if search:
        df = df[df.apply(lambda r: search in str(r.values), axis=1)]

    if location_filter != "전체":
        df = df[df["위치"] == location_filter]

    if status_filter != "전체":
        df = df[df["상태"] == status_filter]

    # ==========================
    # 카테고리 탭
    # ==========================
    categories = df["카테고리"].unique().tolist()
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
                    f"{상태아이콘} {row['물품명']} "
                    f"({row['수량']} {row['단위']})"
                ):

                    st.write(f"📂 카테고리: {row['카테고리']}")
                    st.write(f"📍 위치: {row['위치']}")
                    st.write(f"⏳ 유통기한: {row['유통기한']}")
                    st.write(f"📉 최소재고: {row['최소재고']}")

                    colA, colB = st.columns(2)

                    with colA:
                        in_qty = st.number_input(
                            "입고 수량",
                            1,
                            key=f"in{row['id']}"
                        )
                        if st.button("입고", key=f"inbtn{row['id']}"):
                            cursor.execute(
                                "UPDATE inventory SET 수량 = 수량 + ? WHERE id=?",
                                (in_qty, row["id"])
                            )
                            cursor.execute("""
                                INSERT INTO transactions
                                (날짜, 물품명, 구분, 수량, 메모)
                                VALUES (?, ?, '입고', ?, '')
                            """, (datetime.now(), row["물품명"], in_qty))
                            conn.commit()
                            st.rerun()

                    with colB:
                        out_qty = st.number_input(
                            "사용 수량",
                            1,
                            key=f"out{row['id']}"
                        )
                        if st.button("사용", key=f"outbtn{row['id']}"):
                            cursor.execute(
                                "UPDATE inventory SET 수량 = 수량 - ? WHERE id=?",
                                (out_qty, row["id"])
                            )
                            cursor.execute("""
                                INSERT INTO transactions
                                (날짜, 물품명, 구분, 수량, 메모)
                                VALUES (?, ?, '사용', ?, '')
                            """, (datetime.now(), row["물품명"], out_qty))
                            conn.commit()
                            st.rerun()

