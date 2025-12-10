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
# タブ2: 宿題一覧（rerun 安全版）
# -----------------------------
with tabs[1]:
    st.markdown(
        "<h1 style='color:#ff7f0e; font-size:36px; font-weight:bold;'>📚 宿題管理　</h1>",
        unsafe_allow_html=True
    )

    left, right = st.columns([1,2])

    # 左: 登録フォーム
    with left:
        st.subheader("宿題の登録")

        # 入力用 session_state 初期化
        for key, default in [
            ("input_subject", ""), ("input_new_subject",""), ("input_content",""),
            ("input_due", date.today()), ("input_status","未着手"),
            ("input_submit_method","Teams"), ("input_submit_method_detail","")
        ]:
            if key not in st.session_state:
                st.session_state[key] = default

        subject = st.selectbox(
            "科目",
            options=st.session_state.subjects,
            index=0 if st.session_state.subjects else None,
            key="input_subject"
        )
        new_subject = st.text_input("（新しい科目を追加する場合）", key="input_new_subject")
        content = st.text_area("宿題内容", height=200, key="input_content")
        due = st.date_input("提出日", value=st.session_state.input_due, key="input_due")
        status = st.selectbox("ステータス", ["未着手","作業中","完了"], index=["未着手","作業中","完了"].index(st.session_state.input_status), key="input_status")
        st.markdown("提出方法")
        submit_method = st.radio(
            "",
            ["Teams","Google Classroom","手渡し","その他"],
            index=["Teams","Google Classroom","手渡し","その他"].index(st.session_state.input_submit_method),
            key="input_submit_method"
        )
        submit_method_detail = st.text_input("その他（具体）", key="input_submit_method_detail") if submit_method=="その他" else ""

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
            st.experimental_rerun()  # 追加後に rerun

    # 右: 一覧表示と操作
    with right:
        hw_list = [h for h in st.session_state.homework if isinstance(h, dict)]
        if not hw_list:
            st.info("登録された宿題はありません。")
        else:
            # ローカル変数 df に変換（session_state に入れない）
            df = pd.DataFrame(hw_list)
            df["due_dt"] = pd.to_datetime(df["due"]).dt.date
            df["created_at_dt"] = pd.to_datetime(df["created_at"])
            df["days_left"] = (df["due_dt"] - date.today()).apply(lambda x: x.days)

            # フィルタリング
            filter_status = st.selectbox("ステータスで絞り込む", ["全て","未着手","作業中","完了"], index=0)
            keyword = st.text_input("キーワード検索（科目・内容）", value="")
            if filter_status != "全て":
                df = df[df["status"] == filter_status]
            if keyword.strip():
                df = df[df["subject"].str.contains(keyword, case=False, na=False) |
                        df["content"].str.contains(keyword, case=False, na=False)]
            df = df.sort_values(["due_dt","created_at_dt"], ascending=[True, False])

            st.markdown(f"登録件数: **{len(df)} 件**")
            upcoming = df[df["days_left"] <= 3]
            if not upcoming.empty:
                st.warning(f"締切が3日以内の宿題が **{len(upcoming)} 件** あります。")
                st.table(upcoming[["subject","content","due_dt","status","submit_method"]])

            # ループ内でフラグだけセット
            if "delete_id" not in st.session_state: st.session_state.delete_id = None
            if "done_id" not in st.session_state: st.session_state.done_id = None
            if "update_status" not in st.session_state: st.session_state.update_status = None

            for _, row in df.reset_index(drop=True).iterrows():
                cols = st.columns([3,3,2,2,2])
                # 情報表示
                with cols[0]:
                    st.markdown(f"**{row['subject']}**")
                    st.write(row['content'])
                    st.write(f"提出日: {row['due_dt'].isoformat()} （残り {row['days_left']} 日）")
                    st.write(f"追加: {pd.to_datetime(row['created_at']).strftime('%Y-%m-%d %H:%M')}")

                with cols[1]:
                    st.write(f"提出方法: {row.get('submit_method','')} {row.get('submit_method_detail','')}")

                # ステータス
                with cols[2]:
                    key_status = f"status_{int(row['id'])}"
                    if key_status not in st.session_state:
                        st.session_state[key_status] = row["status"]
                    new_status = st.selectbox("", ["未着手","作業中","完了"],
                                              index=["未着手","作業中","完了"].index(st.session_state[key_status]),
                                              key=key_status)
                    if new_status != row["status"]:
                        st.session_state.update_status = {"id": row["id"], "status": new_status}

                # 完了ボタン
                with cols[3]:
                    if st.button("完了にする", key=f"done_{int(row['id'])}"):
                        st.session_state.done_id = row["id"]

                # 削除ボタン
                with cols[4]:
                    if st.button("削除", key=f"del_{int(row['id'])}"):
                        st.session_state.delete_id = row["id"]

            # ループ外でまとめて処理
            # フラグ初期化
            rerun_needed = False
            
            # ループ内でフラグだけ立てる
            for _, row in df.reset_index(drop=True).iterrows():
                cols = st.columns([3,3,2,2,2])
                with cols[3]:
                    if st.button("完了にする", key=f"done_{int(row['id'])}"):
                        st.session_state.done_id = row["id"]
                        rerun_needed = True
                with cols[4]:
                    if st.button("削除", key=f"del_{int(row['id'])}"):
                        st.session_state.delete_id = row["id"]
                        rerun_needed = True
            
            # ループ外でまとめて処理
            if st.session_state.done_id is not None:
                for h in st.session_state.homework:
                    if h["id"] == st.session_state.done_id:
                        h["status"] = "完了"
                drive_save_json(HOMEWORK_FILE, st.session_state.homework)
                st.session_state.done_id = None
            
            if st.session_state.delete_id is not None:
                st.session_state.homework = [h for h in st.session_state.homework if h["id"] != st.session_state.delete_id]
                drive_save_json(HOMEWORK_FILE, st.session_state.homework)
                st.session_state.delete_id = None
            
            # ループ外で一度だけ rerun
            if rerun_needed:
                st.experimental_rerun()


st.markdown("---")
st.caption("※ Google Drive API による完全クラウド永続化版アプリです")













