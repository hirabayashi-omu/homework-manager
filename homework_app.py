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
FOLDER_ID = "1O7F8ZWvRJCjRVZZ5iyrcXmFQGx2VEYjG"
TIMETABLE_FILE = "timetable.json"
HOMEWORK_FILE = "homework.json"
SUBJECT_FILE = "subjects.json"

# -----------------------------
# Drive API 接続
# -----------------------------
@st.cache_resource
def get_drive_service():
    creds_info = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

def drive_find_file(filename):
    service = get_drive_service()
    results = service.files().list(
        q=f"name='{filename}' and trashed=false",
        spaces="drive",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None

def drive_save_json(filename, data):
    service = get_drive_service()
    try:
        file_id = drive_find_file(filename)
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/json")
        if file_id:
            service.files().update(fileId=file_id, media_body=media, supportsAllDrives=True).execute()
        else:
            body = {"name": filename, "parents": [FOLDER_ID]}
            service.files().create(body=body, media_body=media, supportsAllDrives=True).execute()
    except Exception as e:
        print(f"[Drive] 保存時の警告: {e}")

def drive_load_json(filename, default):
    service = get_drive_service()
    file_id = drive_find_file(filename)
    if not file_id:
        return default
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    try:
        return json.loads(fh.read().decode("utf-8"))
    except Exception:
        return default

# -----------------------------
# Streamlit 設定
# -----------------------------
st.set_page_config(page_title="共有ドライブ版：時間割＆宿題管理", layout="wide")

# -----------------------------
# session_state 初期化
# -----------------------------
def init_session_state():
    # 宿題
    if "homework" not in st.session_state:
        loaded_hw = drive_load_json(HOMEWORK_FILE, [])
        for h in loaded_hw:
            if "due" not in h: h["due"] = date.today().isoformat()
            if "created_at" not in h: h["created_at"] = datetime.now().isoformat()
        st.session_state.homework = loaded_hw

    # 科目
    if "subjects" not in st.session_state:
        loaded_subs = drive_load_json(SUBJECT_FILE, [])
        st.session_state.subjects = loaded_subs if loaded_subs else ["数学","物理","化学","英語","日本史","情報","機械設計"]

    # フラグ
    for flag in ["new_hw_added","delete_id","done_id","update_status"]:
        if flag not in st.session_state:
            st.session_state[flag] = False if "new_hw_added" in flag else None

init_session_state()

# -----------------------------
# UI: タイトル & タブ
# -----------------------------
st.title("個人管理/クラス共有：時間割 & 宿題管理アプリ")
tabs = st.tabs(["📝 時間割入力","📚 宿題一覧"])

# -----------------------------
# タブ2: 宿題管理
# -----------------------------
with tabs[1]:
    left, right = st.columns([1,2])

    # 左: 登録フォーム
    with left:
        st.subheader("宿題の登録")
        subject = st.selectbox("科目", st.session_state.subjects, index=0)
        new_subject = st.text_input("（新しい科目を追加する場合）")
        content = st.text_area("宿題内容")
        due = st.date_input("提出日", value=date.today())
        status = st.selectbox("ステータス", ["未着手","作業中","完了"], index=0)
        submit_method = st.radio("提出方法", ["Teams","Google Classroom","手渡し","その他"])
        submit_method_detail = st.text_input("その他（具体）") if submit_method=="その他" else ""

        if st.button("宿題を追加", key="add_homework"):
            use_subject = new_subject.strip() if new_subject.strip() else subject
            if use_subject not in st.session_state.subjects:
                st.session_state.subjects.append(use_subject)
                st.session_state.subjects.sort()
                with st.spinner("Google Drive に保存中…"):
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
            with st.spinner("Google Drive に保存中…"):
                drive_save_json(HOMEWORK_FILE, st.session_state.homework)
            st.session_state.new_hw_added = True

    # 右: 一覧表示と操作
    with right:
        df = pd.DataFrame(st.session_state.homework)
        if not df.empty:
            df["due_dt"] = pd.to_datetime(df["due"]).dt.date
            df["created_at_dt"] = pd.to_datetime(df["created_at"])
            df = df.sort_values(["due_dt","created_at_dt"], ascending=[True, False])

            for idx, row in df.reset_index(drop=True).iterrows():
                cols = st.columns([3,2,1,1])
                cols[0].write(f"**{row['subject']}**: {row['content'][:50]}...")
                cols[1].write(f"提出日: {row['due']} / ステータス: {row['status']}")
                if cols[2].button("完了", key=f"done_{row['id']}_{idx}"):
                    st.session_state.done_id = row["id"]
                if cols[3].button("削除", key=f"del_{row['id']}_{idx}"):
                    st.session_state.delete_id = row["id"]

    # -----------------------------
    # ループ外でまとめて処理
    # -----------------------------
    rerun_needed = False

    if st.session_state.get("new_hw_added"):
        st.session_state.new_hw_added = False
        rerun_needed = True

    if st.session_state.get("delete_id") is not None:
        st.session_state.homework = [h for h in st.session_state.homework if h["id"] != st.session_state.delete_id]
        with st.spinner("Google Drive に保存中…"):
            drive_save_json(HOMEWORK_FILE, st.session_state.homework)
        st.session_state.delete_id = None
        rerun_needed = True

    if st.session_state.get("done_id") is not None:
        for h in st.session_state.homework:
            if h["id"] == st.session_state.done_id:
                h["status"] = "完了"
        with st.spinner("Google Drive に保存中…"):
            drive_save_json(HOMEWORK_FILE, st.session_state.homework)
        st.session_state.done_id = None
        rerun_needed = True

    if st.session_state.get("update_status") is not None:
        for h in st.session_state.homework:
            if h["id"] == st.session_state.update_status["id"]:
                h["status"] = st.session_state.update_status["status"]
        with st.spinner("Google Drive に保存中…"):
            drive_save_json(HOMEWORK_FILE, st.session_state.homework)
        st.session_state.update_status = None
        rerun_needed = True

    if rerun_needed:
        st.experimental_rerun()

st.markdown("---")
st.caption("※ Google Drive API による完全クラウド永続化版アプリです")
