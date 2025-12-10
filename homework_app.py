import streamlit as st
import os, json, io
from datetime import date, datetime
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import time

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
    service = build("drive", "v3", credentials=creds)
    return service

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
    try:
        file_id = drive_find_file(filename)
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/json")
        service = get_drive_service()
        if file_id:
            service.files().update(
                fileId=file_id,
                media_body=media,
                supportsAllDrives=True
            ).execute()
        else:
            body = {"name": filename, "parents": [FOLDER_ID]}
            service.files().create(
                body=body,
                media_body=media,
                supportsAllDrives=True
            ).execute()
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
# Session State 初期化
# -----------------------------
def init_session_state():
    if "timetable" not in st.session_state:
        default_tt = {"月":["","","",""], "火":["","","",""], "水":["","","",""], "木":["","","",""], "金":["","","",""]}
        loaded_tt = drive_load_json(TIMETABLE_FILE, default_tt)
        for d in loaded_tt:
            if not isinstance(loaded_tt[d], list) or len(loaded_tt[d]) != 4:
                loaded_tt[d] = [""]*4
        st.session_state.timetable = loaded_tt

    if "homework" not in st.session_state:
        loaded_hw = drive_load_json(HOMEWORK_FILE, [])
        if isinstance(loaded_hw, list):
            for h in loaded_hw:
                h.setdefault("due", date.today().isoformat())
                h.setdefault("created_at", datetime.now().isoformat())
            st.session_state.homework = loaded_hw
        else:
            st.session_state.homework = []

    if "subjects" not in st.session_state:
        loaded_subs = drive_load_json(SUBJECT_FILE, [])
        if isinstance(loaded_subs, list) and loaded_subs:
            st.session_state.subjects = loaded_subs
        else:
            subs = set()
            for vals in st.session_state.timetable.values():
                for s in vals:
                    if isinstance(s,str) and s.strip():
                        subs.add(s.strip())
            for c in ["数学","物理","化学","英語","日本史","情報","機械設計"]:
                subs.add(c)
            st.session_state.subjects = sorted(list(subs))
            drive_save_json(SUBJECT_FILE, st.session_state.subjects)

    for flag in ["new_hw_added", "delete_id", "done_id", "update_status"]:
        if flag not in st.session_state:
            st.session_state[flag] = False if flag=="new_hw_added" else None

init_session_state()

# -----------------------------
# Streamlit 設定
# -----------------------------
st.set_page_config(page_title="時間割＆宿題管理", layout="wide")
st.title("個人管理/クラス共有：時間割 & 宿題管理アプリ")

tabs = st.tabs(["📝 時間割入力", "📚 宿題一覧"])

# -----------------------------
# タブ1: 時間割入力
# -----------------------------
with tabs[0]:
    st.markdown("<h2>📝 時間割入力</h2>", unsafe_allow_html=True)
    days = ["月","火","水","木","金"]
    period_labels = ["1/2限","3/4限","5/6限","7/8限"]
    col1, col2 = st.columns([3,1])

    with col1:
        for d in days:
            with st.expander(f"{d}曜日"):
                cols = st.columns(4)
                for i, c in enumerate(cols):
                    key = f"tt_{d}_{i}"
                    if key not in st.session_state:
                        st.session_state[key] = st.session_state.timetable[d][i]
                    st.text_input(f"{period_labels[i]}", key=key)

    with col2:
        if st.button("時間割を保存"):
            for d in days:
                st.session_state.timetable[d] = [st.session_state[f"tt_{d}_{i}"] for i in range(4)]
            with st.spinner("Google Drive に保存中…しばらくお待ちください"):
                drive_save_json(TIMETABLE_FILE, st.session_state.timetable)
                subs = set(st.session_state.subjects)
                for vals in st.session_state.timetable.values():
                    for s in vals:
                        if isinstance(s,str) and s.strip():
                            subs.add(s.strip())
                st.session_state.subjects = sorted(list(subs))
                drive_save_json(SUBJECT_FILE, st.session_state.subjects)
            st.success("時間割を保存しました！")

    st.markdown("---")
    df_preview = pd.DataFrame({d: st.session_state.timetable[d] for d in days}, index=period_labels)
    st.dataframe(df_preview, use_container_width=True)

# -----------------------------
# タブ2: 宿題一覧
# -----------------------------
with tabs[1]:
    st.markdown("<h2>📚 宿題管理</h2>", unsafe_allow_html=True)
    left, right = st.columns([1,2])

    # --- 左: 登録フォーム ---
    with left:
        st.subheader("宿題の登録")
        for key, default in [("input_subject", ""), ("input_new_subject",""), ("input_content",""), ("input_due", date.today()), 
                             ("input_status","未着手"), ("input_submit_method","Teams"), ("input_submit_method_detail","")]:
            if key not in st.session_state:
                st.session_state[key] = default

        subject = st.selectbox("科目", options=st.session_state.subjects, index=0 if st.session_state.subjects else None, key="input_subject")
        new_subject = st.text_input("新しい科目", key="input_new_subject")
        content = st.text_area("宿題内容", height=200, key="input_content")
        due = st.date_input("提出日", value=st.session_state.input_due, key="input_due")
        status = st.selectbox("ステータス", ["未着手","作業中","完了"], index=["未着手","作業中","完了"].index(st.session_state.input_status), key="input_status")
        st.markdown("提出方法")
        submit_method = st.radio("", ["Teams","Google Classroom","手渡し","その他"], index=["Teams","Google Classroom","手渡し","その他"].index(st.session_state.input_submit_method), key="input_submit_method")
        submit_method_detail = st.text_input("その他（具体）", key="input_submit_method_detail") if submit_method=="その他" else ""

    # --- 右: 一覧表示 ---
    with right:
        df = pd.DataFrame(st.session_state.homework)
        if not df.empty:
            df["due_dt"] = pd.to_datetime(df["due"]).dt.date
            df["created_at_dt"] = pd.to_datetime(df["created_at"])
            today_dt = date.today()
            df["days_left"] = (df["due_dt"] - today_dt).apply(lambda x: x.days)
            df = df.sort_values(["due_dt","created_at_dt"], ascending=[True, False])
        else:
            df = pd.DataFrame()

    # --- 共通処理関数 ---
    def add_homework():
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
        with st.spinner("Google Drive に保存中…しばらくお待ちください"):
            drive_save_json(HOMEWORK_FILE, st.session_state.homework)
        st.session_state.new_hw_added = True

    # --- ボタン ---
    if st.button("宿題を追加"):
        add_homework()

    # --- 宿題一覧操作 ---
    if not df.empty:
        for idx, row in df.reset_index(drop=True).iterrows():
            col1, col2, col3 = st.columns([3,1,1])
            with col1:
                st.markdown(f"**{row['subject']}**: {row['content'][:50]}... (提出: {row['due']})")
            with col2:
                if st.button("完了にする", key=f"done_{row['id']}_{idx}"):
                    st.session_state.done_id = row["id"]
            with col3:
                if st.button("削除", key=f"del_{row['id']}_{idx}"):
                    st.session_state.delete_id = row["id"]

    # --- ループ外処理 ---
    rerun_needed = False
    if st.session_state.get("new_hw_added"):
        st.session_state.new_hw_added = False
        rerun_needed = True
    if st.session_state.get("delete_id") is not None:
        st.session_state.homework = [h for h in st.session_state.homework if h["id"] != st.session_state.delete_id]
        with st.spinner("削除処理中…しばらくお待ちください"):
            drive_save_json(HOMEWORK_FILE, st.session_state.homework)
        st.session_state.delete_id = None
        rerun_needed = True
    if st.session_state.get("done_id") is not None:
        for h in st.session_state.homework:
            if h["id"] == st.session_state.done_id:
                h["status"] = "完了"
        with st.spinner("更新中…しばらくお待ちください"):
            drive_save_json(HOMEWORK_FILE, st.session_state.homework)
        st.session_state.done_id = None
        rerun_needed = True

    if rerun_needed:
        st.experimental_rerun()

st.markdown("---")
st.caption("※ Google Drive API による完全クラウド永続化版アプリです")
