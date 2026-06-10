import os
from pathlib import Path
import streamlit as st
from google import genai
from google.genai import types

# 1. 網頁頁面設定
st.set_page_config(page_title="醫療專科 雲端 AI 語音轉錄系統", layout="centered")
st.title("🩺 醫療專科 雲端 AI 語音轉錄系統")
st.subheader("運行環境: 雲端完全託管 (支援醫學術語強化)")

# 2. 讀取 Google AI API Key
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.error("🔑 尚未偵測到 GEMINI_API_KEY！請在 Streamlit Cloud 後台設定。")
else:
    client = genai.Client(api_key=api_key)

    st.info("💡 系統已針對智慧醫療（FHIR, SNOMED CT, PACS 等）進行術語識別優化。")
    
    # 檔案上傳
    uploaded_file = st.file_uploader("請選擇並上傳會議或演講音訊", type=["m4a", "mp3", "wav", "mp4"])

    if uploaded_file is not None:
        st.audio(uploaded_file)
        
        # 💡 自動動態生成下載檔名（例如：會議記錄.m4a -> 會議記錄.txt）
        original_filename = Path(uploaded_file.name).stem  # 取得不含副檔名的主檔名
        download_filename = f"{original_filename}.txt"    # 組合出新的 txt 檔名
        
        # 3. 建立專屬的醫療術語強化提示詞
        with st.expander("🩺 醫療資訊專家提示詞設定 (已啟用)", expanded=True):
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

        # 4. 開始執行轉錄
        if st.button("🚀 開始智慧醫療語音轉錄", type="primary"):
            with st.spinner("正在由雲端 Gemini 醫療領域模型進行深度轉錄與校正..."):
                try:
                    audio_bytes = uploaded_file.read()
                    audio_part = types.Part.from_bytes(
                        data=audio_bytes,
                        mime_type=uploaded_file.type,
                    )
                    
                    # 呼叫 Gemini 2.5 模型
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[
                            medical_prompt,
                            audio_part
                        ]
                    )
                    
                    # 將轉錄結果存入 st.session_state 確保重新渲染時資料不會消失
                    st.session_state["transcript_output"] = response.text
                    st.success("✨ 轉錄與術語校正完成！")
                    
                except Exception as e:
                    st.error(f"❌ 轉錄過程中發生錯誤: {e}")

        # 5. 顯示結果與提供下載（若 session_state 中有結果才顯示）
        if "transcript_output" in st.session_state:
            st.markdown("### 📝 轉錄文本結果")
            transcript_text = st.session_state["transcript_output"]
            st.text_area("結果預覽：", value=transcript_text, height=400)
            
            # 動態帶入 download_filename
            st.download_button(
                label=f"📥 下載醫療會議轉錄檔 ({download_filename})",
                data=transcript_text,
                file_name=download_filename,
                mime="text/plain"
            )
