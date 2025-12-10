import streamlit as st
import json
import os
from datetime import date

TT_DB = "timetable.json"
HW_DB = "homework.json"

# ---- Utility ----
def load(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==== DB読み込み ====
timetable = load(TT_DB, {})

# 安全な初期化
if "subjects" not in timetable:
    timetable["subjects"] = []

if "table" not in timetable:
    timetable["table"] = {}

homework = load(HW_DB, {"list": []})

st.title("時間割 & 宿題管理アプリ")

tabs = st.tabs(["⏰ 時間割入力（セル直接入力）", "📚 宿題ページ"])


# ======================================================
# 1) 時間割ページ
# ======================================================
with tabs[0]:
    st.header("時間割（表内を直接入力）")

    days = ["月", "火", "水", "木", "金"]
    periods = ["1/2限", "3/4限", "5/6限", "7/8限"]

    timetable_data = timetable["table"]

    for d in days:
        st.markdown(f"### {d}曜日")
        cols = st.columns(len(periods))

        for i, p in enumerate(periods):
            key = f"{d}-{p}"
            current = timetable_data.get(key, "")

            with cols[i]:
                st.write(f"**{p}**")
                new_val = st.text_input(
                    f"{key}",
                    value=current,
                    label_visibility="collapsed",
                    placeholder="科目名"
                )
                timetable_data[key] = new_val

    if st.button("時間割を保存"):
        timetable["table"] = timetable_data
        save(TT_DB, timetable)
        st.success("保存しました！")


# ======================================================
# 2) 宿題ページ
# ======================================================
with tabs[1]:
    st.header("宿題を登録")

    # 時間割から自動抽出した科目一覧（空白除外）
    used_subjects = sorted(
        list({v for v in timetable["table"].values() if v.strip() != ""})
    )

    if not used_subjects:
        st.warning("時間割に科目が入力されていません。先に時間割を入力してください。")
    else:
        subject = st.selectbox("科目", used_subjects)
        content = st.text_area("内容")
        deadline = st.date_input("提出日", date.today())

        if st.button("追加"):
            homework["list"].append(
                {
                    "subject": subject,
                    "content": content,
                    "deadline": str(deadline),
                    "status": "未着手",
                }
            )
            save(HW_DB, homework)
            st.success("登録しました！")
            st.rerun()

    st.subheader("宿題一覧（締切順）")

    hw_list = sorted(homework["list"], key=lambda x: x["deadline"])

    if not hw_list:
        st.info("宿題がまだありません。")
    else:
        for i, hw in enumerate(hw_list):
            st.markdown(
                f"### {hw['subject']} — {hw['deadline']}\n{hw['content']}"
            )
            new_status = st.selectbox(
                f"ステータス変更 {i}",
                ["未着手", "作業中", "完了"],
                index=["未着手", "作業中", "完了"].index(hw["status"])
            )
            if new_status != hw["status"]:
                hw["status"] = new_status
                save(HW_DB, homework)
                st.rerun()

            if st.button(f"削除 {i}"):
                homework["list"].remove(hw)
                save(HW_DB, homework)
                st.rerun()
