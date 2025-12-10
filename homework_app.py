# homework_manager.py
# -*- coding: utf-8 -*-
"""
永続化バグ修正版: 時間割 & 宿題管理アプリ
保存: 作業ディレクトリに JSON ファイルを作成して永続化（ローカル実行推奨）
"""

import streamlit as st
import json
import os
from datetime import date, datetime
import pandas as pd
import io

# -------------------------
# ファイル名（変更可）
# -------------------------
TIMETABLE_FILE = "timetable.json"
HOMEWORK_FILE = "homework.json"
SUBJECT_FILE = "subjects.json"

st.set_page_config(page_title="時間割＆宿題管理アプリ", layout="wide")

# -------------------------
# JSONユーティリティ
# -------------------------
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, data):
    # ensure directory exists (for future-proof)
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# -------------------------
# 起動時の初期化（session_state にロード）
# -------------------------
def init_session_state():
    # timetable: dict { "月": [...], ... }
    if "timetable" not in st.session_state:
        tt_default = {"月":["","","",""], "火":["","","",""], "水":["","","",""], "木":["","","",""], "金":["","","",""]}
        loaded_tt = load_json(TIMETABLE_FILE, tt_default)
        # guard: if file corrupted, fallback to default
        if not isinstance(loaded_tt, dict):
            loaded_tt = tt_default
        # ensure each day has 4 slots
        for d in ["月","火","水","木","金"]:
            v = loaded_tt.get(d, [""]*4)
            if not isinstance(v, list) or len(v) != 4:
                loaded_tt[d] = [""]*4
        st.session_state.timetable = loaded_tt

    # homework: list of dicts
    if "homework" not in st.session_state:
        loaded_hw = load_json(HOMEWORK_FILE, [])
        if not isinstance(loaded_hw, list):
            loaded_hw = []
        else:
            # keep only dict entries
            loaded_hw = [x for x in loaded_hw if isinstance(x, dict)]
        # Normalize keys (add missing)
        for h in loaded_hw:
            if "due" not in h or not h["due"]:
                h["due"] = date.today().isoformat()
            if "created_at" not in h and "created" in h:
                h["created_at"] = h.pop("created")
            if "created_at" not in h:
                h["created_at"] = datetime.now().isoformat()
        st.session_state.homework = loaded_hw

    # subjects: list
    if "subjects" not in st.session_state:
        loaded_subs = load_json(SUBJECT_FILE, None)
        if isinstance(loaded_subs, list) and loaded_subs:
            st.session_state.subjects = loaded_subs
        else:
            # generate from timetable + defaults
            subs = set()
            for vals in st.session_state.timetable.values():
                for s in vals:
                    if isinstance(s, str) and s.strip():
                        subs.add(s.strip())
            for c in ["数学","物理","化学","英語","日本史","情報","機械設計"]:
                subs.add(c)
            st.session_state.subjects = sorted(list(subs))
            # save initial subjects
            save_json(SUBJECT_FILE, st.session_state.subjects)

init_session_state()


# -------------------------
# UI
# -------------------------
st.title("時間割 & 宿題管理アプリ）")
tabs = st.tabs(["時間割入力", "宿題一覧"])

# ---- タブ: 時間割入力 ----
with tabs[0]:
    st.header("時間割入力（保存するとローカルに保存されます）")
    col1, col2 = st.columns([3,1])
    days = ["月","火","水","木","金"]
    period_labels = ["1/2限","3/4限","5/6限","7/8限"]

    # 左：入力グリッド
    with col1:
        timetable_temp = {}
        for d in days:
            with st.expander(f"{d}曜日"):
                cols = st.columns(4)
                # session keys: tt_{d}_{i}
                for i, c in enumerate(cols):
                    key = f"tt_{d}_{i}"
                    # initialize UI key with saved timetable value (only if absent)
                    if key not in st.session_state:
                        st.session_state[key] = st.session_state.timetable.get(d, [""]*4)[i]
                    # show text input bound to session_state key
                    st.text_input(f"{d} {period_labels[i]}", key=key)

    # 右：操作
    with col2:
        if st.button("時間割を保存"):
            # collect from keys and save to st.session_state.timetable
            for d in days:
                vals = []
                for i in range(4):
                    key = f"tt_{d}_{i}"
                    vals.append(st.session_state.get(key, ""))
                st.session_state.timetable[d] = vals
            save_json(TIMETABLE_FILE, st.session_state.timetable)
            # update subjects file as well (collect non-empty subjects)
            subs = set(st.session_state.subjects)
            for vals in st.session_state.timetable.values():
                for s in vals:
                    if isinstance(s, str) and s.strip():
                        subs.add(s.strip())
            st.session_state.subjects = sorted(list(subs))
            save_json(SUBJECT_FILE, st.session_state.subjects)
            st.success("時間割を保存しました。")

        if st.button("時間割を初期化（空にする）"):
            for d in days:
                st.session_state.timetable[d] = [""]*4
                # clear UI keys too
                for i in range(4):
                    key = f"tt_{d}_{i}"
                    st.session_state[key] = ""
            save_json(TIMETABLE_FILE, st.session_state.timetable)
            save_json(SUBJECT_FILE, st.session_state.subjects)
            st.success("時間割を初期化しました。")

    # プレビュー
    st.markdown("---")
    df_preview = pd.DataFrame({d: st.session_state.timetable.get(d, [""]*4) for d in days}, index=period_labels)
    st.dataframe(df_preview, use_container_width=True)

    # Export / Import
    st.markdown("---")
    st.subheader("時間割のエクスポート / インポート")
    if st.download_button("時間割をJSONでダウンロード", json.dumps(st.session_state.timetable, ensure_ascii=False, indent=2).encode("utf-8"), file_name="timetable.json", mime="application/json"):
        pass

    uploaded_tt = st.file_uploader("時間割JSONをインポート", type=["json"])
    if uploaded_tt is not None:
        try:
            data = json.load(uploaded_tt)
            if isinstance(data, dict):
                # normalize to 4 slots
                for d in days:
                    v = data.get(d, [""]*4)
                    if not isinstance(v, list) or len(v) != 4:
                        data[d] = [""]*4
                st.session_state.timetable = data
                save_json(TIMETABLE_FILE, st.session_state.timetable)
                # rebuild subject list and save
                subs = set(st.session_state.subjects)
                for vals in st.session_state.timetable.values():
                    for s in vals:
                        if isinstance(s, str) and s.strip():
                            subs.add(s.strip())
                st.session_state.subjects = sorted(list(subs))
                save_json(SUBJECT_FILE, st.session_state.subjects)
                st.success("インポート完了しました。")
                st.experimental_rerun()
            else:
                st.error("辞書型の JSON をアップロードしてください。")
        except Exception as e:
            st.error(f"読み込みエラー: {e}")

# ---- タブ: 宿題一覧 ----
with tabs[1]:
    st.header("宿題ページ（追加・編集・削除・CSV出力）")
    left, right = st.columns([1,2])

    # 左: 入力フォーム
    with left:
        st.subheader("宿題の登録")
        subject = st.selectbox("科目", options=st.session_state.subjects, index=0 if st.session_state.subjects else None)
        new_subject = st.text_input("（新しい科目を追加する場合）", value="")
        if st.button("科目を追加"):
            ns = new_subject.strip()
            if ns:
                if ns not in st.session_state.subjects:
                    st.session_state.subjects.append(ns)
                    st.session_state.subjects.sort()
                    save_json(SUBJECT_FILE, st.session_state.subjects)
                    st.success(f"科目「{ns}」を追加しました。")
                else:
                    st.info("その科目は既に存在します。")
            else:
                st.warning("科目名を入力してください。")

        content = st.text_area("宿題内容", placeholder="例: レポート 3ページ、問題集 p10-15")
        due = st.date_input("提出日", value=date.today())
        status = st.selectbox("ステータス", options=["未着手","作業中","完了"], index=0)
        st.markdown("提出方法")
        submit_method = st.radio("", options=["Teams","Google Classroom","手渡し","その他"], index=0)
        submit_method_detail = ""
        if submit_method == "その他":
            submit_method_detail = st.text_input("その他（具体）", value="")

        if st.button("宿題を追加"):
            if not (subject or new_subject.strip()):
                st.error("科目を選択するか、新しい科目を入力してください。")
            elif not content.strip():
                st.error("宿題内容を入力してください。")
            else:
                use_subject = new_subject.strip() if new_subject.strip() else subject
                if use_subject not in st.session_state.subjects:
                    st.session_state.subjects.append(use_subject)
                    st.session_state.subjects.sort()
                    save_json(SUBJECT_FILE, st.session_state.subjects)

                hw = {
                    "id": int(datetime.now().timestamp() * 1000),
                    "subject": use_subject,
                    "content": content.strip(),
                    "due": due.isoformat(),
                    "status": status,
                    "submit_method": submit_method,
                    "submit_method_detail": submit_method_detail,
                    "created_at": datetime.now().isoformat()
                }
                st.session_state.homework.append(hw)
                save_json(HOMEWORK_FILE, st.session_state.homework)
                st.success("宿題を追加しました。")

    # 右: 一覧表示と操作
    with right:
        st.subheader("宿題一覧")
        hw_list = st.session_state.homework.copy()
        # clean
        hw_list = [h for h in hw_list if isinstance(h, dict)]
        # ensure keys
        for h in hw_list:
            if "due" not in h or not h["due"]:
                h["due"] = date.today().isoformat()
            if "created_at" not in h:
                h["created_at"] = datetime.now().isoformat()

        if not hw_list:
            st.info("登録された宿題はありません。")
        else:
            df = pd.DataFrame(hw_list)
            df["due_dt"] = pd.to_datetime(df["due"]).dt.date
            df["created_at_dt"] = pd.to_datetime(df["created_at"])
            # filters
            filter_status = st.selectbox("ステータスで絞り込む", options=["全て","未着手","作業中","完了"], index=0)
            keyword = st.text_input("キーワード検索（科目・内容）", value="")

            if filter_status != "全て":
                df = df[df["status"] == filter_status]
            if keyword.strip():
                df = df[df["subject"].str.contains(keyword, case=False, na=False) | df["content"].str.contains(keyword, case=False, na=False)]

            # sort and days left
            df = df.sort_values(["due_dt","created_at_dt"], ascending=[True, False])
            today = date.today()
            df["days_left"] = (df["due_dt"] - pd.to_datetime(today).date()).apply(lambda x: x.days)

            st.markdown(f"登録件数: **{len(df)} 件**")
            upcoming = df[df["days_left"] <= 3]
            if not upcoming.empty:
                st.warning(f"締切が3日以内の宿題が **{len(upcoming)} 件** あります。")
                st.table(upcoming[["subject","content","due_dt","status","submit_method"]])

            # show interactive list (each row has actions)
            for _idx, row in df.reset_index(drop=True).iterrows():
                st.markdown("---")
                cols = st.columns([3,3,2,2,2])
                with cols[0]:
                    st.markdown(f"**{row['subject']}** — {row['content']}")
                    st.write(f"提出: {row['due_dt'].isoformat()} （残り {row['days_left']} 日）")
                with cols[1]:
                    st.write(f"提出方法: {row.get('submit_method','')} {row.get('submit_method_detail','')}")
                    st.write(f"追加: {pd.to_datetime(row['created_at']).strftime('%Y-%m-%d %H:%M')}")
                with cols[2]:
                    # status selector
                    key_status = f"status_{int(row['id'])}"
                    if key_status not in st.session_state:
                        st.session_state[key_status] = row["status"]
                    new_status = st.selectbox("", options=["未着手","作業中","完了"], index=["未着手","作業中","完了"].index(st.session_state[key_status]), key=key_status)
                    if new_status != row["status"]:
                        # apply change to original list
                        for h in st.session_state.homework:
                            if h.get("id") == row["id"]:
                                h["status"] = new_status
                                save_json(HOMEWORK_FILE, st.session_state.homework)
                                st.success("ステータスを更新しました。")
                                break
                with cols[3]:
                    if st.button(f"完了にする_{int(row['id'])}", key=f"done_{int(row['id'])}"):
                        for h in st.session_state.homework:
                            if h.get("id") == row["id"]:
                                h["status"] = "完了"
                                save_json(HOMEWORK_FILE, st.session_state.homework)
                                st.success("完了にしました。")
                                break
                with cols[4]:
                    if st.button(f"削除_{int(row['id'])}", key=f"del_{int(row['id'])}"):
                        st.session_state.homework = [h for h in st.session_state.homework if h.get("id") != row["id"]]
                        save_json(HOMEWORK_FILE, st.session_state.homework)
                        st.success("削除しました。")
                        # We don't rerun automatically; user can refresh list via action

            # CSV ダウンロード（2形式）
            st.markdown("---")
            st.markdown("### エクスポート")
            export_df = df.drop(columns=["due_dt","created_at_dt","days_left"], errors="ignore").copy()
            export_df = export_df.astype(str)

            # UTF-8 BOM (utf-8-sig) - modern Excel & mac friendly
            csv_utf8 = export_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("CSV (UTF-8 BOM)", data=csv_utf8, file_name="homework_utf8bom.csv", mime="text/csv")

            # Shift_JIS (cp932) - Windows Excel 互換
            csv_cp932 = export_df.to_csv(index=False).encode("cp932", errors="replace")
            st.download_button("CSV (Shift_JIS / Excel)", data=csv_cp932, file_name="homework_shiftjis.csv", mime="text/csv")

# フッター
st.markdown("---")
st.caption("※ ローカルで実行することを推奨します。クラウドで動かす場合は永続化方法を別途用意してください。")
