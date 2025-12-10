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
        creds_info, scopes=["https://www.googleapis.com/auth/drive"]
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
                fileId=file_id, media_body=media, supportsAllDrives=True
            ).execute()
        else:
            body = {"name": filename, "parents": [FOLDER_ID]}
            service.files().create(
                body=body, media_body=media, supportsAllDrives=True
            ).execute()
    except Exception as e:
        st.warning(f"[Drive] 保存時の警告: {e}")

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

# -----------------------------
# session_state 初期化
# -----------------------------
def init_session_state():
    # --- 時間割 ---
    if "timetable" not in st.session_state:
        default_tt = {"月":["","","",""], "火":["","","",""], "水":["","","",""], "木":["","","",""], "金":["","","",""]}
        loaded_tt = drive_load_json(TIMETABLE_FILE, default_tt)
        for d in loaded_tt:
            if not isinstance(loaded_tt[d], list) or len(loaded_tt[d]) != 4:
                loaded_tt[d] = [""]*4
        st.session_state.timetable = loaded_tt

    # --- 宿題 ---
    if "homework" not in st.session_state:
        loaded_hw = drive_load_json(HOMEWORK_FILE, [])
        safe_hw = []
        if isinstance(loaded_hw, list):
            for h in loaded_hw:
                if not isinstance(h, dict):
                    continue  # dictでない場合はスキップ
                # due の補正
                due_val = h.get("due")
                if not isinstance(due_val, str) or not due_val.strip():
                    h["due"] = date.today().isoformat()
                # created_at の補正
                created_val = h.get("created_at")
                if not isinstance(created_val, str) or not created_val.strip():
                    h["created_at"] = datetime.now().isoformat()
                # status 補正
                if "status" not in h or h["status"] not in ["未着手","作業中","完了"]:
                    h["status"] = "未着手"
                safe_hw.append(h)
        st.session_state.homework = safe_hw

    # --- 科目 ---
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

    # --- その他フラグ ---
    for flag in ["new_hw_added", "delete_id", "done_id", "update_status"]:
        if flag not in st.session_state:
            st.session_state[flag] = None


init_session_state()

# -----------------------------
# Streamlit 設定
# -----------------------------
st.set_page_config(page_title="共有ドライブ版：時間割＆宿題管理", layout="wide")
st.title("個人管理/クラス共有：時間割 & 宿題管理アプリ")
tabs = st.tabs(["📝 時間割入力", "📚 宿題一覧"])

# =============================
# タブ1: 時間割入力
# =============================
with tabs[0]:
    st.markdown("<h1 style='color:#1f77b4; font-size:36px;'>📝 時間割入力</h1>", unsafe_allow_html=True)
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
            drive_save_json(TIMETABLE_FILE, st.session_state.timetable)

            # subjects 更新
            subs = set(st.session_state.subjects)
            for vals in st.session_state.timetable.values():
                for s in vals:
                    if isinstance(s,str) and s.strip():
                        subs.add(s.strip())
            st.session_state.subjects = sorted(list(subs))
            drive_save_json(SUBJECT_FILE, st.session_state.subjects)

            st.success("時間割を Google Drive に保存しました！")

    st.markdown("---")
    st.markdown("### プレビュー")
    df_preview = pd.DataFrame({d: st.session_state.timetable[d] for d in days}, index=period_labels)
    st.dataframe(df_preview, use_container_width=True)

    # JSON アップロード
    uploaded_file = st.file_uploader("ここに JSON ファイルをドラッグ＆ドロップ", type=["json"])
    if uploaded_file is not None:
        try:
            loaded_tt = json.load(uploaded_file)
            for d in loaded_tt:
                if d in st.session_state.timetable:
                    for i in range(4):
                        st.session_state.timetable[d][i] = loaded_tt[d][i] if i<len(loaded_tt[d]) else ""
            st.success("時間割を読み込みました！")
        except Exception as e:
            st.error(f"JSON 読み込みエラー: {e}")

# =============================
# タブ2: 宿題管理
# =============================
with tabs[1]:
    st.markdown("<h1 style='color:#ff7f0e; font-size:36px;'>📚 宿題管理</h1>", unsafe_allow_html=True)
    left, right = st.columns([1,2])

    # ---- 左: 登録フォーム ----
    with left:
        st.subheader("宿題の登録")
        subject = st.selectbox("科目", options=st.session_state.subjects)
        new_subject = st.text_input("（新しい科目を追加する場合）")
        content = st.text_area("宿題内容", height=200)
        due = st.date_input("提出日", value=date.today())
        status = st.selectbox("ステータス", ["未着手","作業中","完了"], index=0)
        st.markdown("提出方法")
        submit_method = st.radio("", ["Teams","Google Classroom","手渡し","その他"], index=0)
        submit_method_detail = st.text_input("その他（具体）") if submit_method=="その他" else ""

        if st.button("宿題を追加"):
            use_subject = new_subject.strip() if new_subject.strip() else subject
            if use_subject not in st.session_state.subjects:
                st.session_state.subjects.append(use_subject)
                st.session_state.subjects.sort()
                drive_save_json(SUBJECT_FILE, st.session_state.subjects)
            hw = {
                "id": int(datetime.now().timestamp()*1000),
                "subject": use_subject,
                "content": content.strip() if content.strip() else "（内容未記入）",
                "due": due.isoformat(),
                "status": status,
                "submit_method": submit_method,
                "submit_method_detail": submit_method_detail.strip(),
                "created_at": datetime.now().isoformat()
            }
            st.session_state.homework.append(hw)
            drive_save_json(HOMEWORK_FILE, st.session_state.homework)
            st.success("宿題を追加しました。")

    # ---- 右: 一覧表示 ----
with right:
    st.subheader("宿題一覧")
    hw_list = st.session_state.homework or []

    if not hw_list:
        st.info("宿題はまだ登録されていません。")
    else:
        df = pd.DataFrame(hw_list)
        df["due_dt"] = pd.to_datetime(df["due"], errors='coerce').dt.date
        df["created_at_dt"] = pd.to_datetime(df["created_at"], errors='coerce')
        today_dt = date.today()
        df["days_left"] = (df["due_dt"] - today_dt).apply(lambda x: x.days if pd.notnull(x) else None)
        df = df.sort_values(["due_dt","created_at_dt"], ascending=[True, False])

        # フィルター
        filter_status = st.selectbox("ステータスで絞り込む", ["全て","未着手","作業中","完了"], index=0)
        keyword = st.text_input("キーワード検索（科目・内容）", value="")
        df_filtered = df.copy()
        if filter_status != "全て":
            df_filtered = df_filtered[df_filtered["status"]==filter_status]
        if keyword.strip():
            df_filtered = df_filtered[
                df_filtered["subject"].str.contains(keyword, case=False, na=False) |
                df_filtered["content"].str.contains(keyword, case=False, na=False)
            ]

        # 直近3日以内ハイライト
        def highlight_due(row):
            return ['background-color: red; color: white;' if row['days_left'] is not None and row['days_left'] <= 3 else '' for _ in row]
        styled = df_filtered[["subject","content","due_dt","status","submit_method","days_left"]].style.apply(highlight_due, axis=1)
        st.dataframe(styled.data.drop(columns=['days_left']), use_container_width=True)

        # 完了・削除ボタン
        for idx, row in df_filtered.iterrows():
            cols = st.columns([3,1,1,1])
            cols[0].markdown(
                f"**{row['subject']}** - {row['content']}<br>"
                f"提出日: {row['due_dt']} / 提出方法: {row['submit_method']} {row.get('submit_method_detail','')}",
                unsafe_allow_html=True
            )
            new_status = cols[1].selectbox(
                "", ["未着手","作業中","完了"], index=["未着手","作業中","完了"].index(row["status"]), key=f"status_{row['id']}"
            )
            if new_status != row["status"]:
                for h in st.session_state.homework:
                    if h["id"] == row["id"]:
                        h["status"] = new_status
                drive_save_json(HOMEWORK_FILE, st.session_state.homework)
                st.experimental_rerun()

            if cols[2].button("完了", key=f"done_{row['id']}"):
                for h in st.session_state.homework:
                    if h["id"] == row["id"]:
                        h["status"] = "完了"
                drive_save_json(HOMEWORK_FILE, st.session_state.homework)
                st.experimental_rerun()

            if cols[3].button("削除", key=f"del_{row['id']}"):
                st.session_state.homework = [h for h in st.session_state.homework if h["id"] != row["id"]]
                drive_save_json(HOMEWORK_FILE, st.session_state.homework)
                st.experimental_rerun()

st.markdown("---")
st.caption("※ Google Drive API による完全クラウド永続化版アプリです")



