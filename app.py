import os
import time
from pathlib import Path
import streamlit as st
from google import genai
from google.genai import types

# 1. 網頁頁面設定
st.set_page_config(page_title="醫療專科 雲端 AI 批次語音轉錄系統", layout="centered")
st.title("🩺 醫療專科 雲端 AI 批次語音轉錄系統")
st.subheader("運行環境: 雲端完全託管 (支援多檔案同時上傳)")

# 依副檔名判斷 MIME 類型（瀏覽器回報的 type 不可靠，例如 m4a 常為 audio/x-m4a 或空值）
MIME_TYPES = {
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
}

# 檔案在 Gemini 雲端處理的最長等待時間（秒）
PROCESSING_TIMEOUT = 600

# 2. 讀取 Google AI API Key（st.secrets 優先；無 secrets.toml 時 st.secrets 會拋錯，改讀環境變數）
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.error("🔑 尚未偵測到 GEMINI_API_KEY！請在 Streamlit Cloud 的 App settings → Secrets 設定。")
else:
    client = genai.Client(api_key=api_key)

    st.info("💡 系統已優化批次處理功能，您可以一次拖入多個音訊檔案進行自動化轉錄。")
    
    # 💡 關鍵更動：開啟 accept_multiple_files=True
    uploaded_files = st.file_uploader(
        "請選擇並上傳一個或多個會議音訊檔案", 
        type=["m4a", "mp3", "wav", "mp4"],
        accept_multiple_files=True
    )

    # 用來存放所有檔案轉錄結果的字典
    if "batch_outputs" not in st.session_state:
        st.session_state["batch_outputs"] = {}
    # 雲端刪除失敗的檔案（需提醒使用者手動處理）
    if "delete_failures" not in st.session_state:
        st.session_state["delete_failures"] = []

    if uploaded_files:
        st.write(f"📋 已選取 {len(uploaded_files)} 個檔案，準備進行批次處理。")
        
        # 3. 建立專屬的醫療術語強化提示詞
        with st.expander("🩺 醫療資訊專家提示詞設定 (已啟用)", expanded=False):
            medical_prompt = st.text_area(
                "給 AI 的指導原則：",
                value=(
                    "你是一位精通智慧醫療、醫療資訊系統（HIS/PACS）與國際醫療資料標準的專業記錄員。\n"
                    "請將這段音訊精準轉錄為繁體中文（台灣習慣用語）。\n"
                    "【特別注意】音訊中包含大量醫療資訊與標準化編碼的專業術語，請務必正確拼寫，例如：\n"
                    "- 醫療資訊交換與編碼標準：FHIR, HL7, DICOM, SNOMED CT, RxNorm, LOINC, ICD-10\n"
                    "- 檢驗與影像系統：PACS (Picture Archiving and Communication System), RIS, HIS, LIS\n"
                    "若遇到英文縮寫，請保持大寫（如 LOINC、FHIR）。不確定的語句請結合醫療與檢驗數據上下文進行合理推斷，保持專門術語的精確度。"
                ),
                height=200
            )

        # 4. 開始批次執行轉錄
        if st.button("🚀 開始批次智慧醫療轉錄", type="primary"):
            # 建立一個進度條
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 清空舊的紀錄
            st.session_state["batch_outputs"] = {}
            st.session_state["delete_failures"] = []
            
            for index, uploaded_file in enumerate(uploaded_files):
                filename = uploaded_file.name
                # 同名檔案加上編號，避免結果互相覆蓋
                result_key = filename
                dup = 2
                while result_key in st.session_state["batch_outputs"]:
                    result_key = f"{Path(filename).stem} ({dup}){Path(filename).suffix}"
                    dup += 1
                step = f"({index+1}/{len(uploaded_files)}): **{result_key}**"
                status_text.markdown(f"⏳ 正在上傳 {step}")
                
                gemini_file = None
                try:
                    suffix = Path(filename).suffix.lower()
                    mime_type = MIME_TYPES.get(suffix)
                    if mime_type is None:
                        raise ValueError(f"不支援的檔案格式「{suffix or '無副檔名'}」，僅支援 {', '.join(MIME_TYPES)}")
                    
                    # 透過 Files API 上傳（避開 inline 資料約 20MB 的請求上限，支援長時間會議錄音）
                    uploaded_file.seek(0)
                    gemini_file = client.files.upload(
                        file=uploaded_file,
                        config=types.UploadFileConfig(mime_type=mime_type, display_name=filename),
                    )
                    
                    # 等待雲端處理完成（設有逾時，避免單一檔案卡住整個批次）
                    status_text.markdown(f"⏳ 雲端處理中 {step}")
                    deadline = time.monotonic() + PROCESSING_TIMEOUT
                    while gemini_file.state == types.FileState.PROCESSING:
                        if time.monotonic() > deadline:
                            raise TimeoutError(f"雲端處理超過 {PROCESSING_TIMEOUT // 60} 分鐘仍未完成")
                        time.sleep(2)
                        gemini_file = client.files.get(name=gemini_file.name)
                    if gemini_file.state == types.FileState.FAILED:
                        raise RuntimeError("Gemini 檔案處理失敗")
                    
                    # 呼叫 Gemini 3.8 Flash 模型
                    status_text.markdown(f"⏳ 轉錄中 {step}")
                    response = client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=[medical_prompt, gemini_file]
                    )
                    
                    # 將結果存入 session_state
                    # response.text 在內容被安全機制阻擋或無輸出時為 None
                    if not response.text:
                        raise RuntimeError("模型未回傳轉錄內容（可能遭安全機制阻擋或輸出為空）")
                    st.session_state["batch_outputs"][result_key] = response.text
                    
                except Exception as e:
                    st.session_state["batch_outputs"][result_key] = f"❌ 轉錄發生錯誤: {e}"
                
                finally:
                    # 轉錄後立即刪除雲端檔案（醫療音訊不留存，否則預設保留 48 小時）
                    if gemini_file is not None:
                        try:
                            client.files.delete(name=gemini_file.name)
                        except Exception as e:
                            st.session_state["delete_failures"].append(f"{result_key}（{gemini_file.name}）：{e}")
                
                # 更新進度條
                progress_bar.progress((index + 1) / len(uploaded_files))
                
            status_text.success("✨ 所有檔案批次處理完成！")
            progress_bar.empty()

        # 5. 顯示批次結果與下載區塊
        if st.session_state["batch_outputs"]:
            st.write("---")
            st.markdown("### 📥 轉錄結果下載與預覽")
            
            if st.session_state["delete_failures"]:
                st.warning(
                    "⚠️ 以下音訊未能從 Gemini 雲端刪除（預設將保留 48 小時），請至 Google AI Studio 手動刪除：\n\n"
                    + "\n".join(f"- {f}" for f in st.session_state["delete_failures"])
                )
            
            # 建立打包合併的文字
            combined_text = ""
            
            # 用分頁 (Tabs) 的方式呈現各個檔案的結果，介面比較整齊
            file_names = list(st.session_state["batch_outputs"].keys())
            tabs = st.tabs(file_names)
            
            for i, filename in enumerate(file_names):
                with tabs[i]:
                    file_text = st.session_state["batch_outputs"][filename]
                    st.text_area(f"{filename} 的轉錄內容", value=file_text, height=300, key=f"txt_{filename}")
                    
                    # 個別下載按鈕（自動對齊檔名）
                    stem_name = Path(filename).stem
                    st.download_button(
                        label=f"📥 下載單檔：{stem_name}.txt",
                        data=file_text,
                        file_name=f"{stem_name}.txt",
                        mime="text/plain",
                        key=f"dl_{filename}"
                    )
                    
                    # 併入總文本
                    combined_text += f"=== 檔案名稱: {filename} ===\n{file_text}\n\n"
            
            # 提供一鍵下載全部合併包的功能
            st.write("---")
            st.download_button(
                label="📦 一鍵下載所有檔案合併轉錄檔 (combined_all.txt)",
                data=combined_text,
                file_name="combined_all.txt",
                mime="text/plain",
                type="secondary"
            )
