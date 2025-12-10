# homework_manager_drive_full.py
# -*- coding: utf-8 -*-
"""
Google Drive 永続化版: 時間割 & 宿題管理アプリ
Streamlit Cloud 対応版。JSON は Drive に保存。
"""

import streamlit as st
import os, json, io
from datetime import date, datetime
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

# -----------------------------
# Google Drive 設定
# -----------------------------
FOLDER_ID = "1O7F8ZWvRJCjRVZZ5iyrcXmFQGx2VEYjG"  # 対象フォルダID
TIMETABLE_FILE = "timetable.json"
HOMEWORK_FILE = "homework.json"
SUBJECT_FILE = "subjects.json"

# -----------------------------
# Drive API 接続
# -----------------------------
@st.cache_resource
def get_drive_service():
    credentials_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not credentials_json:
        st.error("環境変数 GOOGLE_CREDENTIALS が設定されていません")
        st.stop()
    try:
        creds_info = json.loads(credentials_json)
    except json.JSONDecodeError:
        st.error("GOOGLE_CREDENTIALS の JSON が不正です")
        st.stop()
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=creds)
    return service

service = get_drive_service()

# -----------------------------
# Drive Utility
# -----------------------------
def drive_find_file(filename):
    query = f"'{FOLDER_ID}' in parents and name='{filename}' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None

def drive_load_json(filename, default):
    file_id = drive_find_file(filename)
    if not file_id:
        return default
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    try:
        fh.seek(0)
        return json.loads(fh.read().decode("utf-8"))
    except Exception:
        return default

def drive_save_json(filename, data):
    file_id = drive_find_file(filename)
    body = {"name": filename, "parents": [FOLDER_ID]}
    content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/json")
    if file_id:
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        service.files().create(body=body, media_body=media).execute()

# -----------------------------
# Streamlit 設定
# -----------------------------
st.set_page_config(page_title="Drive永続化版：時間割＆宿題管理", layout="wide")

# -----------------------------
# session_state 初期化
# -----------------------------
def init_session_state():
    # 時間割
    if "timetable" not in st.session_state:
        default_tt = {"月":["","","",""], "火":["","","",""], "水":["","","",""], "木":["","","",""], "金":["","","",""]}
        loaded_tt = drive_load_json(TIMETABLE_FILE, default_tt)
        for d in ["月","火","水","木","金"]:
            v = loaded_tt.get(d, [""]*4)
            if not isinstance(v, list) or len(v) != 4:
                loaded_tt[d] = [""]*4
        st.session_state.timetable = loaded_tt

    # 宿題
    if "homework" not in st.session_state:
        loaded_hw = drive_load_json(HOMEWORK_FILE, [])
        if isinstance(loaded_hw, list):
            for h in loaded_hw:
                if "due" not in h or not h["due"]:
                    h["due"] = date.today().isoformat()
                if "created_at" not in h:
                    h["created_at"] = datetime.now().isoformat()
            st.session_state.homework = loaded_hw
        else:
            st.session_state.homework = []

    # 科目
    if "subjects" not in st.session_state:
        loaded_subs = drive_load_json(SUBJECT_FILE, [])
        if isinstance(loaded_subs, list) and loaded_subs:
            st.session_state.subjects = loaded_subs
        else:
            subs = set()
            for vals in st.session_state.timetable.values():
                for s in vals:
                    if isinstance(s, str) and s.strip():
                        subs.add(s.strip())
            for c in ["数学","物理","化学","英語","日本史","情報","機械設計"]:
                subs.add(c)
            st.session_state.subjects = sorted(list(subs))
            drive_save_json(SUBJECT_FILE, st.session_state.subjects)

init_session_state()

# -----------------------------
# UI: タイトル & タブ
# -----------------------------
st.title("Google Drive 永続化版：時間割 & 宿題管理アプリ")
tabs = st.tabs(["時間割入力", "宿題一覧"])

# -----------------------------
# タブ1: 時間割入力
# -----------------------------
with tabs[0]:
    st.header("時間割入力（Google Drive 保存）")
    days = ["月","火","水","木","金"]
    period_labels = ["1/2限","3/4限","5/6限","7/8限"]
    col1, col2 = st.columns([3,1])

    # 入力グリッド
    with col1:
        for d in days:
            with st.expander(f"{d}曜日"):
                cols = st.columns(4)
                for i, c in enumerate(cols):
                    key = f"tt_{d}_{i}"
                    if key not in st.session_state:
                        st.session_state[key] = st.session_state.timetable[d][i]
                    st.text_input(f"{period_labels[i]}", key=key)

    # 操作
    with col2:
        if st.button("時間割を保存"):
            for d in days:
                st.session_state.timetable[d] = [st.session_state[f"tt_{d}_{i}"] for i in range(4)]
            drive_save_json(TIMETABLE_FILE, st.session_state.timetable)
            # 科目更新
            subs = set(st.session_state.subjects)
            for vals in st.session_state.timetable.values():
                for s in vals:
                    if isinstance(s,str) and s.strip():
                        subs.add(s.strip())
            st.session_state.subjects = sorted(list(subs))
            drive_save_json(SUBJECT_FILE, st.session_state.subjects)
            st.success("時間割を Google Drive に保存しました！")

    # プレビュー
    st.markdown("---")
    st.markdown("### プレビュー")
    df_preview = pd.DataFrame({d: st.session_state.timetable[d] for d in days}, index=period_labels)
    st.dataframe(df_preview, use_container_width=True)

    # JSON エクスポート / インポート
    st.markdown("---")
    st.subheader("時間割のエクスポート / インポート")
    if st.download_button("時間割をJSONでダウンロード",
                          json.dumps(st.session_state.timetable, ensure_ascii=False, indent=2).encode("utf-8"),
                          file_name="timetable.json", mime="application/json"):
        pass

    uploaded_tt = st.file_uploader("時間割JSONをインポート", type=["json"])
    if uploaded_tt is not None:
        try:
            data = json.load(uploaded_tt)
            if isinstance(data, dict):
                for d in days:
                    v = data.get(d, [""]*4)
                    if not isinstance(v, list) or len(v) != 4:
                        data[d] = [""]*4
                st.session_state.timetable = data
                drive_save_json(TIMETABLE_FILE, st.session_state.timetable)
                # 科目更新
                subs = set(st.session_state.subjects)
                for vals in st.session_state.timetable.values():
                    for s in vals:
                        if isinstance(s,str) and s.strip():
                            subs.add(s.strip())
                st.session_state.subjects = sorted(list(subs))
                drive_save_json(SUBJECT_FILE, st.session_state.subjects)
                st.success("インポート完了しました。")
                st.experimental_rerun()
            else:
                st.error("辞書型 JSON をアップロードしてください。")
        except Exception as e:
            st.error(f"読み込みエラー: {e}")

# -----------------------------
# タブ2: 宿題一覧
# -----------------------------
with tabs[1]:
    st.header("宿題管理（Google Drive 永続化）")
    left, right = st.columns([1,2])

    # 左: 登録フォーム
    with left:
        st.subheader("宿題の登録")
        subject = st.selectbox("科目", options=st.session_state.subjects, index=0 if st.session_state.subjects else None)
        new_subject = st.text_input("（新しい科目を追加する場合）", value="")
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
                    drive_save_json(SUBJECT_FILE, st.session_state.subjects)

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
                drive_save_json(HOMEWORK_FILE, st.session_state.homework)
                st.success("宿題を追加しました。")

    # 右: 一覧表示と操作
    with right:
        hw_list = [h for h in st.session_state.homework if isinstance(h, dict)]
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
            filter_status = st.selectbox("ステータスで絞り込む", options=["全て","未着手","作業中","完了"], index=0)
            keyword = st.text_input("キーワード検索（科目・内容）", value="")

            if filter_status != "全て":
                df = df[df["status"] == filter_status]
            if keyword.strip():
                df = df[df["subject"].str.contains(keyword, case=False, na=False) |
                        df["content"].str.contains(keyword, case=False, na=False)]

            df = df.sort_values(["due_dt","created_at_dt"], ascending=[True, False])
            today_dt = date.today()
            df["days_left"] = (df["due_dt"] - today_dt).apply(lambda x: x.days)

            st.markdown(f"登録件数: **{len(df)} 件**")
            upcoming = df[df["days_left"] <= 3]
            if not upcoming.empty:
                st.warning(f"締切が3日以内の宿題が **{len(upcoming)} 件** あります。")
                st.table(upcoming[["subject","content","due_dt","status","submit_method"]])

            # 行ごとの操作
            for _, row in df.reset_index(drop=True).iterrows():
                st.markdown("---")
                cols = st.columns([3,3,2,2,2])
                with cols[0]:
                    st.markdown(f"**{row['subject']}** — {row['content']}")
                    st.write(f"提出: {row['due_dt'].isoformat()} （残り {row['days_left']} 日）")
                with cols[1]:
                    st.write(f"提出方法: {row.get('submit_method','')} {row.get('submit_method_detail','')}")
                    st.write(f"追加: {pd.to_datetime(row['created_at']).strftime('%Y-%m-%d %H:%M')}")
                with cols[2]:
                    key_status = f"status_{int(row['id'])}"
                    if key_status not in st.session_state:
                        st.session_state[key_status] = row["status"]
                    new_status = st.selectbox("", options=["未着手","作業中","完了"],
                                              index=["未着手","作業中","完了"].index(st.session_state[key_status]),
                                              key=key_status)
                    if new_status != row["status"]:
                        for h in st.session_state.homework:
                            if h["id"] == row["id"]:
                                h["status"] = new_status
                                drive_save_json(HOMEWORK_FILE, st.session_state.homework)
                                st.success("ステータスを更新しました。")
                                break
                with cols[3]:
                    if st.button(f"完了にする_{int(row['id'])}", key=f"done_{int(row['id'])}"):
                        for h in st.session_state.homework:
                            if h["id"] == row["id"]:
                                h["status"] = "完了"
                                drive_save_json(HOMEWORK_FILE, st.session_state.homework)
                                st.success("完了にしました。")
                                break
                with cols[4]:
                    if st.button(f"削除_{int(row['id'])}", key=f"del_{int(row['id'])}"):
                        st.session_state.homework = [h for h in st.session_state.homework if h["id"] != row["id"]]
                        drive_save_json(HOMEWORK_FILE, st.session_state.homework)
                        st.success("削除しました。")

            # CSV ダウンロード
            st.markdown("---")
            st.markdown("### エクスポート")
            export_df = df.drop(columns=["due_dt","created_at_dt","days_left"], errors="ignore").astype(str)
            csv_utf8 = export_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("CSV (UTF-8 BOM)", data=csv_utf8, file_name="homework_utf8bom.csv", mime="text/csv")
            csv_cp932 = export_df.to_csv(index=False).encode("cp932", errors="replace")
            st.download_button("CSV (Shift_JIS / Excel)", data=csv_cp932, file_name="homework_shiftjis.csv", mime="text/csv")

st.markdown("---")
st.caption("※ Google Drive API による完全クラウド永続化版アプリです")
