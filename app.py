import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

st.set_page_config(page_title="치과 재고관리 시스템", layout="wide")

# -----------------------------
# DB 연결
# -----------------------------
conn = sqlite3.connect("inventory.db", check_same_thread=False)

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
    날짜 TEXT,
    메모 TEXT
)
""")
conn.commit()

# -----------------------------
# 데이터 로드
# -----------------------------
def load_data():
    return pd.read_sql("SELECT * FROM inventory", conn)

# -----------------------------
# 상태 계산 (안전버전)
# -----------------------------
def calculate_status(row):
    today = datetime.today().date()

    if row["유통기한"] and str(row["유통기한"]).strip() != "":
        try:
            exp = pd.to_datetime(row["유통기한"]).date()
            if exp < today:
                return "만료"
            elif exp <= today + timedelta(days=30):
                return "임박"
        except:
            pass

    if row["수량"] <= row["최소재고"]:
        return "부족"

    return "정상"

# -----------------------------
# 상단 UI
# -----------------------------
st.title("📦 치과 재고관리 시스템")

df = load_data()

if not df.empty:
    df["상태"] = df.apply(calculate_status, axis=1)
else:
    df["상태"] = ""

# -----------------------------
# 통계 카드
# -----------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("전체 품목", len(df))
col2.metric("만료", (df["상태"] == "만료").sum())
col3.metric("임박", (df["상태"] == "임박").sum())
col4.metric("부족", (df["상태"] == "부족").sum())

st.divider()

# -----------------------------
# 검색
# -----------------------------
search = st.text_input("🔍 검색 (이름/카테고리/위치)")

if search:
    df = df[
        df["품목명"].str.contains(search, case=False, na=False) |
        df["카테고리"].str.contains(search, case=False, na=False) |
        df["위치"].str.contains(search, case=False, na=False)
    ]

# -----------------------------
# 카테고리 탭
# -----------------------------
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
                st.write(f"⏳ 유통기한: {row['유통기한']}")
                st.write(f"📉 최소재고: {row['최소재고']}")

                # -------------------------
                # 최소재고 수정 버튼
                # -------------------------
                if st.button("✏ 최소재고 수정", key=f"edit_min_{row['id']}"):
                    st.session_state[f"edit_mode_{row['id']}"] = True

                if st.session_state.get(f"edit_mode_{row['id']}"):
                    new_min = st.number_input(
                        "새 최소재고",
                        min_value=0,
                        value=int(row["최소재고"]),
                        key=f"new_min_{row['id']}"
                    )

                    if st.button("저장", key=f"save_min_{row['id']}"):
                        conn.execute(
                            "UPDATE inventory SET 최소재고=? WHERE id=?",
                            (new_min, row["id"])
                        )
                        conn.commit()
                        st.success("최소재고가 수정되었습니다.")
                        st.session_state[f"edit_mode_{row['id']}"] = False
                        st.rerun()

                st.divider()

                colA, colB = st.columns(2)

                # -------------------------
                # 입고
                # -------------------------
                with colA:
                    in_qty = st.number_input(
                        "입고 수량",
                        min_value=1,
                        step=1,
                        key=f"in_{row['id']}"
                    )

                    memo_in = st.text_input(
                        "메모(선택)",
                        key=f"memo_in_{row['id']}"
                    )

                    if st.button("입고", key=f"btn_in_{row['id']}"):
                        conn.execute(
                            "UPDATE inventory SET 수량=? WHERE id=?",
                            (row["수량"] + in_qty, row["id"])
                        )
                        conn.execute(
                            "INSERT INTO logs (품목명, 구분, 수량, 날짜, 메모) VALUES (?,?,?,?,?)",
                            (row["품목명"], "입고", in_qty,
                             datetime.now().strftime("%Y-%m-%d %H:%M"),
                             memo_in)
                        )
                        conn.commit()
                        st.success("입고 완료")
                        st.rerun()

                # -------------------------
                # 사용
                # -------------------------
                with colB:
                    out_qty = st.number_input(
                        "사용 수량",
                        min_value=1,
                        step=1,
                        key=f"out_{row['id']}"
                    )

                    memo_out = st.text_input(
                        "메모(선택)",
                        key=f"memo_out_{row['id']}"
                    )

                    if st.button("사용", key=f"btn_out_{row['id']}"):
                        if row["수량"] >= out_qty:
                            conn.execute(
                                "UPDATE inventory SET 수량=? WHERE id=?",
                                (row["수량"] - out_qty, row["id"])
                            )
                            conn.execute(
                                "INSERT INTO logs (품목명, 구분, 수량, 날짜, 메모) VALUES (?,?,?,?,?)",
                                (row["품목명"], "사용", out_qty,
                                 datetime.now().strftime("%Y-%m-%d %H:%M"),
                                 memo_out)
                            )
                            conn.commit()
                            st.success("사용 완료")
                            st.rerun()
                        else:
                            st.error("재고 부족")
