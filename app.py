import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="치과 재고관리", layout="wide")

@st.cache_data
def load_data():
    return pd.read_excel("1단계_기본골격.xlsx")

if "inventory" not in st.session_state:
    st.session_state.inventory = load_data()

if "logs" not in st.session_state:
    st.session_state.logs = {}

st.title("🦷 치과 재고관리 앱")

menu = st.sidebar.radio("메뉴", ["재고 목록", "물품 등록"])

# -----------------------
# 물품 등록
# -----------------------
if menu == "물품 등록":
    st.subheader("📦 물품 등록")

    name = st.text_input("물품명")
    qty = st.number_input("수량", min_value=0)
    unit = st.text_input("단위")

    if st.button("저장"):
        if name and unit:
            new = pd.DataFrame({
                "물품명": [name],
                "수량": [qty],
                "단위": [unit]
            })
            st.session_state.inventory = pd.concat(
                [st.session_state.inventory, new],
                ignore_index=True
            )
            st.success("저장 완료")

# -----------------------
# 재고 목록
# -----------------------
if menu == "재고 목록":
    st.subheader("📋 현재 재고")

    selected = st.selectbox(
        "물품 선택",
        st.session_state.inventory["물품명"]
    )

    item_index = st.session_state.inventory[
        st.session_state.inventory["물품명"] == selected
    ].index[0]

    item = st.session_state.inventory.loc[item_index]

    st.write(f"### {item['물품명']}")
    st.write(f"현재 수량: {item['수량']} {item['단위']}")

    col1, col2 = st.columns(2)

    with col1:
        in_qty = st.number_input("입고 수량", min_value=1, key="in")
        if st.button("입고"):
            st.session_state.inventory.at[item_index, "수량"] += in_qty
            st.session_state.logs.setdefault(selected, []).append({
                "날짜": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "구분": "입고",
                "수량": in_qty
            })
            st.success("입고 완료")

    with col2:
        out_qty = st.number_input("사용 수량", min_value=1, key="out")
        if st.button("사용"):
            st.session_state.inventory.at[item_index, "수량"] -= out_qty
            st.session_state.logs.setdefault(selected, []).append({
                "날짜": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "구분": "사용",
                "수량": out_qty
            })
            st.success("사용 완료")

    st.divider()
    st.subheader("📜 입출고 기록")

    logs = st.session_state.logs.get(selected, [])
    if logs:
        st.table(pd.DataFrame(logs))
    else:
        st.write("기록 없음")
