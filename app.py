st.write(load_data().columns)
st.stop()
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

st.set_page_config(page_title="치과 재고관리 시스템", layout="wide")

# ---------------------------
# DB 연결
# ---------------------------
conn = sqlite3.connect("inventory.db", check_same_thread=False)

conn.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    category TEXT,
    qty INTEGER DEFAULT 0,
    unit TEXT DEFAULT '개',
    expiry TEXT,
    min_qty INTEGER DEFAULT 0,
    location TEXT DEFAULT ''
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    type TEXT,
    qty INTEGER,
    date TEXT,
    memo TEXT
)
""")
conn.commit()

# ---------------------------
# 데이터 로드
# ---------------------------
def load_data():
    return pd.read_sql("SELECT * FROM inventory", conn)

# ---------------------------
# 상태 계산 (완전 안전)
# ---------------------------
def calculate_status(row):
    today = datetime.today().date()

    # 유통기한 처리
    if row["expiry"]:
        try:
            exp = pd.to_datetime(row["expiry"]).date()
            if exp < today:
                return "만료"
            elif exp <= today + timedelta(days=30):
                return "임박"
        except:
            pass

    # 최소재고 체크
    if row["qty"] <= row["min_qty"]:
        return "부족"

    return "정상"

# ---------------------------
# 메인
# ---------------------------
st.title("📦 치과 재고관리 시스템")

df = load_data()

if not df.empty:
    df["status"] = df.apply(calculate_status, axis=1)
else:
    df["status"] = ""

# ---------------------------
# 통계 카드
# ---------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("전체 품목", len(df))
c2.metric("만료", (df["status"] == "만료").sum())
c3.metric("임박", (df["status"] == "임박").sum())
c4.metric("부족", (df["status"] == "부족").sum())

st.divider()

# ---------------------------
# 검색
# ---------------------------
search = st.text_input("🔍 검색 (이름/카테고리/위치)")

if search:
    df = df[
        df["name"].str.contains(search, case=False, na=False) |
        df["category"].str.contains(search, case=False, na=False) |
        df["location"].str.contains(search, case=False, na=False)
    ]

# ---------------------------
# 카테고리
# ---------------------------
categories = ["진료용 소모품", "일반 비품", "치과기구", "치과설비"]
tabs = st.tabs(categories)

for i, cat in enumerate(categories):
    with tabs[i]:
        df_cat = df[df["category"] == cat]

        if df_cat.empty:
            st.info("항목 없음")
            continue

        for _, row in df_cat.iterrows():

            icon = ""
            if row["status"] == "만료":
                icon = "🔴"
            elif row["status"] == "임박":
                icon = "🟡"
            elif row["status"] == "부족":
                icon = "⚠️"

            with st.expander(
                f"{icon} {row['name']} ({row['qty']} {row['unit']}) - {row['status']}"
            ):

                st.write(f"📂 카테고리: {row['category']}")
                st.write(f"📍 위치: {row['location']}")
                st.write(f"⏳ 유통기한: {row['expiry']}")
                st.write(f"📉 최소재고: {row['min_qty']}")

                # -----------------
                # 최소재고 수정 버튼
                # -----------------
                if st.button("✏ 최소재고 수정", key=f"edit_{row['id']}"):
                    st.session_state[f"edit_{row['id']}"] = True

                if st.session_state.get(f"edit_{row['id']}"):
                    new_min = st.number_input(
                        "새 최소재고",
                        min_value=0,
                        value=int(row["min_qty"]),
                        key=f"min_input_{row['id']}"
                    )

                    if st.button("저장", key=f"save_{row['id']}"):
                        conn.execute(
                            "UPDATE inventory SET min_qty=? WHERE id=?",
                            (new_min, row["id"])
                        )
                        conn.commit()
                        st.session_state[f"edit_{row['id']}"] = False
                        st.success("수정 완료")
                        st.rerun()

                st.divider()

                colA, colB = st.columns(2)

                # 입고
                with colA:
                    in_qty = st.number_input(
                        "입고 수량",
                        min_value=1,
                        step=1,
                        key=f"in_{row['id']}"
                    )

                    if st.button("입고", key=f"btn_in_{row['id']}"):
                        conn.execute(
                            "UPDATE inventory SET qty=? WHERE id=?",
                            (row["qty"] + in_qty, row["id"])
                        )
                        conn.execute(
                            "INSERT INTO logs (name,type,qty,date,memo) VALUES (?,?,?,?,?)",
                            (row["name"], "입고", in_qty,
                             datetime.now().strftime("%Y-%m-%d %H:%M"),
                             "")
                        )
                        conn.commit()
                        st.success("입고 완료")
                        st.rerun()

                # 사용
                with colB:
                    out_qty = st.number_input(
                        "사용 수량",
                        min_value=1,
                        step=1,
                        key=f"out_{row['id']}"
                    )

                    if st.button("사용", key=f"btn_out_{row['id']}"):
                        if row["qty"] >= out_qty:
                            conn.execute(
                                "UPDATE inventory SET qty=? WHERE id=?",
                                (row["qty"] - out_qty, row["id"])
                            )
                            conn.execute(
                                "INSERT INTO logs (name,type,qty,date,memo) VALUES (?,?,?,?,?)",
                                (row["name"], "사용", out_qty,
                                 datetime.now().strftime("%Y-%m-%d %H:%M"),
                                 "")
                            )
                            conn.commit()
                            st.success("사용 완료")
                            st.rerun()
                        else:
                            st.error("재고 부족")
