# homework_manager.py
# -*- coding: utf-8 -*-
"""
時間割＆宿題管理アプリ（Streamlit）
機能:
- タブ切替（時間割入力 / 宿題管理）
- 時間割: 月〜金 × 4ブロック(1/2限,3/4限,5/6限,7/8限) を入力・保存・読み込み・エクスポート
- 宿題: 科目選択(時間割から自動取得または追加)、内容、提出日、ステータス(未着手/作業中/完了)、提出方法を登録
- 宿題は追加・編集(ステータス変更)・削除可能
- CSVダウンロード（宿題一覧）
- 追加機能: 提出方法ラジオ, 締切3日以内の宿題をハイライト
保存: 作業ディレクトリに JSON ファイルを作成して永続化します
"""

import streamlit as st
import json
import os
from datetime import date, datetime, timedelta
import pandas as pd
import io

# ファイル名
TIMETABLE_FILE = "timetable.json"
HOMEWORK_FILE = "homework.json"

st.set_page_config(page_title="時間割＆宿題管理アプリ", layout="wide")

# ---- ユーティリティ ----
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8-sig") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def init_session_state():
    if "timetable" not in st.session_state:
        st.session_state.timetable = load_json(TIMETABLE_FILE, default={
            "月": ["", "", "", ""],
            "火": ["", "", "", ""],
            "水": ["", "", "", ""],
            "木": ["", "", "", ""],
            "金": ["", "", "", ""],
        })
    if "homework" not in st.session_state:
        loaded = load_json(HOMEWORK_FILE, default=[])
        # --- ここが追加の安全化パッチ ---
        if not isinstance(loaded, list):
            loaded = []
        else:
            # list 内に文字列など不正データが混ざっていたら除外
            loaded = [x for x in loaded if isinstance(x, dict)]
        # -----------------------------------
        st.session_state.homework = loaded
    if "subjects" not in st.session_state:
        # 科目一覧は時間割の値から自動生成（空文字は除外）
        subs = set()
        for day_vals in st.session_state.timetable.values():
            for s in day_vals:
                if s and s.strip():
                    subs.add(s.strip())
        # 代表的な科目候補も追加
        default_candidates = ["数学", "物理", "化学", "英語", "日本史", "情報", "機械設計"]
        for c in default_candidates:
            subs.add(c)
        st.session_state.subjects = sorted(list(subs))

init_session_state()

# ---- UI ----
st.title("時間割 & 宿題管理アプリ（Streamlit）")
st.markdown("個人や仲間内で共有して使える簡易の宿題管理アプリです。")

tabs = st.tabs(["時間割入力", "宿題一覧"])

# --------- タブ1: 時間割入力 ---------
with tabs[0]:
    st.header("時間割入力（保存するとローカルに保存されます）")
    col1, col2 = st.columns([3,1])
    with col1:
        st.markdown("#### 曜日 × 時限（1/2限、3/4限、5/6限、7/8限）")
        # 表形式で入力
        days = ["月", "火", "水", "木", "金"]
        period_labels = ["1/2限", "3/4限", "5/6限", "7/8限"]
        # Build a simple grid
        timetable_changes = {}
        for d in days:
            with st.expander(f"{d}曜日"):
                cols = st.columns(4)
                values = st.session_state.timetable.get(d, [""]*4)
                new_vals = []
                for i, c in enumerate(cols):
                    new_val = c.text_input(f"{d} {period_labels[i]}", value=values[i], key=f"tt_{d}_{i}")
                    new_vals.append(new_val)
                timetable_changes[d] = new_vals

    with col2:
        st.markdown("#### 操作")
        if st.button("時間割を保存"):
            st.session_state.timetable = timetable_changes
            save_json(TIMETABLE_FILE, st.session_state.timetable)
            # update subjects
            subs = set(st.session_state.subjects)
            for day_vals in st.session_state.timetable.values():
                for s in day_vals:
                    if s and s.strip():
                        subs.add(s.strip())
            st.session_state.subjects = sorted(list(subs))
            st.success("時間割を保存しました。")
        if st.button("時間割を初期化（空にする）"):
            st.session_state.timetable = {d: ["", "", "", ""] for d in days}
            save_json(TIMETABLE_FILE, st.session_state.timetable)
            st.session_state.subjects = []
            st.success("時間割を空にしました。")
        st.caption("※ ファイルはアプリと同じフォルダに保存されます。")

    st.markdown("---")
    st.markdown("#### 現在の時間割プレビュー")
    df_preview = pd.DataFrame(
        {d: st.session_state.timetable.get(d, [""]*4) for d in days},
        index=period_labels
    )
    st.dataframe(df_preview)

    # Export/Import
    st.markdown("---")
    st.markdown("#### エクスポート / インポート")
    if st.button("時間割をJSONでダウンロード"):
        json_bytes = json.dumps(st.session_state.timetable, ensure_ascii=False, indent=2).encode("utf-8-sig")
        st.download_button("ダウンロード（JSON）", data=json_bytes, file_name="timetable.json", mime="application/json")
    uploaded_tt = st.file_uploader("時間割JSONをインポート", type=["json"])
    if uploaded_tt is not None:
        try:
            data = json.load(uploaded_tt)
            # simple validation
            if isinstance(data, dict):
                st.session_state.timetable = data
                save_json(TIMETABLE_FILE, st.session_state.timetable)
                # update subjects
                subs = set()
                for day_vals in st.session_state.timetable.values():
                    for s in day_vals:
                        if s and s.strip():
                            subs.add(s.strip())
                st.session_state.subjects = sorted(list(subs))
                st.success("インポート完了しました。")
            else:
                st.error("形式が正しくありません。辞書型のJSONをアップロードしてください。")
        except Exception as e:
            st.error(f"JSONの読み込みに失敗しました: {e}")

# --------- タブ2: 宿題一覧 ---------
with tabs[1]:
    st.header("宿題ページ")
    st.markdown("宿題の追加・編集・削除、CSV出力ができます。")

    # 左: 入力フォーム、右: 一覧
    left, right = st.columns([1,2])

    with left:
        st.subheader("宿題の登録")
        # 科目の選択肢に時間割から抽出した科目を含める
        subject = st.selectbox("科目", options=st.session_state.subjects, index=0 if st.session_state.subjects else None)
        # 入力して科目を追加することも可能
        new_subject = st.text_input("（新しい科目を追加する場合はこちらに入力）", value="")
        if new_subject and st.button("科目を追加"):
            if new_subject.strip() not in st.session_state.subjects:
                st.session_state.subjects.append(new_subject.strip())
                st.session_state.subjects.sort()
                st.success(f"科目「{new_subject.strip()}」を追加しました。")
            else:
                st.info("その科目は既に存在します。")

        content = st.text_area("宿題内容", placeholder="例: レポート 3ページ分、問題集 p10-15 など")
        due = st.date_input("提出日", value=date.today())
        status = st.selectbox("ステータス", options=["未着手", "作業中", "完了"])
        # オリジナル機能: 提出方法ラジオ
        st.markdown("提出方法")
        submit_method = st.radio("", options=["Teams", "Google Classroom", "手渡し", "その他"], index=0)
        if submit_method == "その他":
            submit_method_detail = st.text_input("その他（具体）", value="")
        else:
            submit_method_detail = ""

        if st.button("宿題を追加"):
            if not (subject or new_subject):
                st.error("科目を選択するか、新しい科目を入力してください。")
            elif not content.strip():
                st.error("宿題内容を入力してください。")
            else:
                use_subject = new_subject.strip() if new_subject.strip() else subject
                if use_subject not in st.session_state.subjects:
                    st.session_state.subjects.append(use_subject)
                    st.session_state.subjects.sort()
                hw = {
                    "id": int(datetime.now().timestamp()*1000),
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
                # clear inputs (re-run will show cleared)
                st.rerun()

        st.markdown("#### クイック操作")
        if st.button("未着手のみ表示（右側フィルタをセット）"):
            st.session_state.filter_status = "未着手"
            st.rerun()
        if st.button("締切3日以内の宿題をハイライト"):
            st.session_state.filter_status = "近い締切"

    with right:
        st.subheader("宿題一覧")
        # フィルタ、ソート
        filter_col, sort_col, search_col = st.columns([1,1,1])
        filter_status = filter_col.selectbox("ステータスで絞り込む", options=["全て", "未着手", "作業中", "完了"], index=0)
        sort_option = sort_col.selectbox("並び替え", options=["提出日（昇順）", "提出日（降順）", "作成日（新しい順）"], index=0)
        keyword = search_col.text_input("キーワード検索（科目・内容）", value="")

        hw_list = st.session_state.homework.copy()

        # --- 安全化パッチ：list内の「文字列データ」や「不正データ」を除外 ---
        cleaned_hw_list = []
        for hw in hw_list:
            if isinstance(hw, dict):        # dict のものだけ採用
                cleaned_hw_list.append(hw)
        # 採用したものだけで置き換える
        hw_list = cleaned_hw_list

        # --- 欠損キーを補完 ---
        for hw in hw_list:
            if "due" not in hw or not hw["due"]:
                hw["due"] = date.today().isoformat()

            if "created_at" not in hw or not hw["created_at"]:
                hw["created_at"] = datetime.now().isoformat()

        df = pd.DataFrame(hw_list)



        df = pd.DataFrame(hw_list)
        if df.empty:
            st.info("登録された宿題はありません。左から追加できます。")
        else:
            # parse dates
            df["due_dt"] = pd.to_datetime(df["due"]).dt.date
            df["created_at_dt"] = pd.to_datetime(df["created_at"])
            # filter by status
            if filter_status != "全て":
                df = df[df["status"] == filter_status]
            # keyword
            if keyword.strip():
                df = df[df["subject"].str.contains(keyword, case=False, na=False) | df["content"].str.contains(keyword, case=False, na=False)]
            # sort
            if sort_option == "提出日（昇順）":
                df = df.sort_values("due_dt", ascending=True)
            elif sort_option == "提出日（降順）":
                df = df.sort_values("due_dt", ascending=False)
            else:
                df = df.sort_values("created_at_dt", ascending=False)

            # Highlight close due dates
            today = date.today()
            df["days_left"] = (df["due_dt"] - pd.to_datetime(today).date()).apply(lambda x: x.days)
            # display summary
            st.markdown(f"登録件数: **{len(df)} 件**")
            # show upcoming (締切3日以内)
            upcoming = df[df["days_left"] <= 3]
            if not upcoming.empty:
                st.warning(f"締切が3日以内の宿題が **{len(upcoming)} 件** あります。")
                st.table(upcoming[["subject", "content", "due_dt", "status", "submit_method"]].head(10))

            # Display table with actions
            # We will allow status変更と削除を行うUIを各行に提供
            for idx, row in df.reset_index(drop=True).iterrows():
                st.markdown("---")
                cols = st.columns([3,3,2,2,2])
                with cols[0]:
                    st.markdown(f"**{row['subject']}** — {row['content']}")
                    st.write(f"提出: {row['due_dt'].isoformat()} （残り {row['days_left']} 日）")
                with cols[1]:
                    st.write(f"提出方法: {row.get('submit_method', '')} {row.get('submit_method_detail','')}")
                    st.write(f"追加: {pd.to_datetime(row['created_at']).strftime('%Y-%m-%d %H:%M')}")
                # status変更
                with cols[2]:
                    new_status = st.selectbox(f"ステータス変更_{row['id']}", options=["未着手", "作業中", "完了"], index=["未着手","作業中","完了"].index(row["status"]))
                    if new_status != row["status"]:
                        if st.button(f"更新_{row['id']}", key=f"upd_{row['id']}"):
                            # update in session_state.homework
                            for h in st.session_state.homework:
                                if h["id"] == row["id"]:
                                    h["status"] = new_status
                                    save_json(HOMEWORK_FILE, st.session_state.homework)
                                    st.success("ステータスを更新しました。")
                                    st.rerun()
                # Mark done quick button
                with cols[3]:
                    if st.button(f"完了にする_{row['id']}", key=f"done_{row['id']}"):
                        for h in st.session_state.homework:
                            if h["id"] == row["id"]:
                                h["status"] = "完了"
                                save_json(HOMEWORK_FILE, st.session_state.homework)
                                st.success("完了にしました。")
                                st.rerun()
                # delete
                with cols[4]:
                    if st.button(f"削除_{row['id']}", key=f"del_{row['id']}"):
                        st.session_state.homework = [h for h in st.session_state.homework if h["id"] != row["id"]]
                        save_json(HOMEWORK_FILE, st.session_state.homework)
                        st.success("削除しました。")
                        st.rerun()

            # CSV ダウンロード
            st.markdown("---")
            st.markdown("### エクスポート")
            export_df = df.drop(columns=["due_dt", "created_at_dt", "days_left"], errors="ignore")
            # ensure string types for JSON-serializable export
            export_df = export_df.astype(str)
            csv_buf = io.StringIO()
            export_df.to_csv(csv_buf, index=False)
            st.download_button("宿題一覧をCSVでダウンロード", data=csv_buf.getvalue().encode("utf-8-sig"), file_name="homework_list.csv", mime="text/csv")

# ---- フッター ----
st.markdown("---")
st.caption("※ このアプリはローカルに JSON を保存します。複数人で共有する場合は、共有場所にこのファイルを置くか、Streamlit Cloud等へデプロイしてURLを共有してください（本課題ではデプロイ不要）。")

