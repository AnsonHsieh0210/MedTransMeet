# 🩺 MedTransMeet：醫療專科雲端 AI 批次語音轉錄系統

以 Streamlit + Google Gemini（`gemini-2.5-flash`）將醫療會議錄音批次轉錄為繁體中文（台灣用語），並強化醫療資訊術語（FHIR、HL7、DICOM、SNOMED CT、LOINC、ICD-10、PACS 等）的辨識。

## 功能
- 一次上傳多個音訊檔（m4a / mp3 / wav / mp4），依序自動轉錄
- 透過 Gemini Files API 上傳，支援長時間會議錄音（不受 inline 20MB 限制）
- 轉錄完成後立即刪除 Gemini 雲端上的音訊檔，不留存醫療資料
- 可自訂醫療提示詞
- 單檔下載 `.txt` 或一鍵下載合併檔 `combined_all.txt`

## 部署到 Streamlit Community Cloud
1. 到 https://share.streamlit.io 選 **Create app**，Repository 選本 repo，Branch `main`，Main file `app.py`
2. 在 **Advanced settings → Secrets** 填入：
   ```toml
   GEMINI_API_KEY = "你的金鑰"
   ```
3. 按 **Deploy**

（另附 `Dockerfile`，也可部署到 Hugging Face Spaces 等支援 Docker 的平台。）

## 本機執行
```bash
pip install -r requirements.txt
export GEMINI_API_KEY=你的金鑰
streamlit run app.py
```

## 隱私提醒
若錄音含病患個資，請使用 Gemini API 付費方案（免費層資料可能被用於改善模型）。
