import streamlit as st
import os, json, io
from datetime import date, datetime
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import time, random

# -----------------------------
# Google Drive 設定
# -----------------------------
FOLDER_ID = "1O7F8ZWvRJCjRVZZ5iyrcXmFQGx2VEYjG" # Shared Drive 内のフォルダIDに変更
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
    """
    JSON データを Google Drive に保存（既存なら update、新規なら create）。
    Shared Drive 対応。エラーは表示しない。
    """
    try:
        file_id = drive_find_file(filename)
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/json")

        if file_id:
            # 既存ファイルを更新
            service.files().update(
                fileId=file_id,
                media_body=media,
                supportsAllDrives=True
            ).execute()
        else:
            # 新規作成
            body = {"name": filename, "parents": [FOLDER_ID]}
            service.files().create(
                body=body,
                media_body=media,
                supportsAllDrives=True
            ).execute()
    except Exception as e:
        # ここで st.error を出さずに無視する
        print(f"[Drive] 保存時の警告: {e}")  # デバッグ用には残せる
        
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
        status, done = downloader.next_chunk()
    fh.seek(0)
    try:
        return json.loads(fh.read().decode("utf-8"))
    except Exception:
        return default

# 削除関数
def delete_homework(hw_id):
    st.session_state.homework = [h for h in st.session_state.homework if h["id"] != hw_id]
    drive_save_json(HOMEWORK_FILE, st.session_state.homework)
    st.success("削除しました。")
    st.experimental_rerun()  # 再描画して一覧を更新



# -----------------------------
# Streamlit 設定
# -----------------------------
st.set_page_config(page_title="共有ドライブ版：時間割＆宿題管理", layout="wide")

# -----------------------------
# session_state 初期化
# -----------------------------
def init_session_state():
    # 時間割
    if "timetable" not in st.session_state:
        default_tt = {"月":["","","",""], "火":["","","",""], "水":["","","",""], "木":["","","",""], "金":["","","",""]}
        loaded_tt = drive_load_json(TIMETABLE_FILE, default_tt)
        for d in loaded_tt:
            if not isinstance(loaded_tt[d], list) or len(loaded_tt[d]) != 4:
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
                    if isinstance(s,str) and s.strip():
                        subs.add(s.strip())
            for c in ["数学","物理","化学","英語","日本史","情報","機械設計"]:
                subs.add(c)
            st.session_state.subjects = sorted(list(subs))
            drive_save_json(SUBJECT_FILE, st.session_state.subjects)

init_session_state()

# -----------------------------
# UI: タイトル & タブ（目立たせ版）
# -----------------------------
st.title("個人管理/クラス共有：時間割 & 宿題管理アプリ")

tabs = st.tabs([
    "📝 時間割入力", 
    "📚 宿題一覧"
])

# -----------------------------
# タブ1: 時間割入力
# -----------------------------
with tabs[0]:
    st.markdown(
        "<h1 style='color:#1f77b4; font-size:36px; font-weight:bold;'>📝 時間割入力　</h1>",
        unsafe_allow_html=True
    )

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
# フラグ初期化（ループ外）
# -----------------------------
for flag in ["new_hw_added", "delete_id", "done_id", "update_status"]:
    if flag not in st.session_state:
        st.session_state[flag] = False if "new_hw_added" in flag else None

# -----------------------------
# 宿題追加ボタン
# -----------------------------
if st.button("宿題を追加"):
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
    st.session_state.new_hw_added = True  # フラグで rerun 指示

# -----------------------------
# 宿題一覧ループ内（削除・完了・ステータス変更）
# -----------------------------
for idx, row in df.reset_index(drop=True).iterrows():
    # ...（表示部分は省略）...

    # 削除ボタン
    if st.button("削除", key=f"del_{int(row['id'])}_{idx}"):
        st.session_state.delete_id = row["id"]

    # 完了ボタン
    if st.button("完了にする", key=f"done_{int(row['id'])}_{idx}"):
        st.session_state.done_id = row["id"]

    # ステータス変更
    if new_status != row["status"]:
        st.session_state.update_status = {"id": row["id"], "status": new_status}

# -----------------------------
# ループ外でまとめて処理
# -----------------------------
rerun_needed = False

# 新規追加
if st.session_state.get("new_hw_added"):
    st.session_state.new_hw_added = False
    rerun_needed = True

# 削除
if st.session_state.get("delete_id") is not None:
    st.session_state.homework = [h for h in st.session_state.homework if h["id"] != st.session_state.delete_id]
    drive_save_json(HOMEWORK_FILE, st.session_state.homework)
    st.success("削除しました。")
    st.session_state.delete_id = None
    rerun_needed = True

# 完了
if st.session_state.get("done_id") is not None:
    for h in st.session_state.homework:
        if h["id"] == st.session_state.done_id:
            h["status"] = "完了"
    drive_save_json(HOMEWORK_FILE, st.session_state.homework)
    st.success("完了にしました。")
    st.session_state.done_id = None
    rerun_needed = True

# ステータス変更
if st.session_state.get("update_status") is not None:
    for h in st.session_state.homework:
        if h["id"] == st.session_state.update_status["id"]:
            h["status"] = st.session_state.update_status["status"]
    drive_save_json(HOMEWORK_FILE, st.session_state.homework)
    st.success("ステータスを更新しました。")
    st.session_state.update_status = None
    rerun_needed = True

# 最終 rerun
if rerun_needed:
    st.experimental_rerun()


st.markdown("---")
st.caption("※ Google Drive API による完全クラウド永続化版アプリです")




















