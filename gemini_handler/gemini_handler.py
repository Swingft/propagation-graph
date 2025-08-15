import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from google_drive_handler import GoogleDriveHandler
import time
from google.api_core import exceptions
from google.generativeai.types import HarmCategory, HarmBlockThreshold

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY must be set in your .env file.")
genai.configure(api_key=API_KEY)


class GeminiHandler:
    # 안전 설정을 가장 낮은 수준으로 조정
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    model = genai.GenerativeModel("gemini-2.5-pro", safety_settings=safety_settings)

    @classmethod
    def ask(cls, prompt_config, retries=3):
        """
        Gemini 모델에 요청을 보내고 응답을 반환합니다.
        API 사용량 초과 시 자동으로 재시도합니다.
        """
        if isinstance(prompt_config, dict):
            user_message = next((msg for msg in prompt_config.get("messages", []) if msg["role"] == "user"), None)
            prompt_text = user_message["content"] if user_message else ""
        else:
            prompt_text = prompt_config

        # --- ✨ 재시도 로직 시작 ---
        for i in range(retries):
            try:
                response = cls.model.generate_content(prompt_text)
                return response.text
            except exceptions.ResourceExhausted as e:
                # --- ✨ 수정된 부분 ---
                # 에러 객체에서 대기 시간을 읽는 대신, 분당 사용량 제한을 피하기 위해 61초간 대기합니다.
                wait_time = 61

                print(f"  ⚠️ Gemini API 사용량 초과. {wait_time}초 후 재시도합니다... ({i + 1}/{retries})")
                time.sleep(wait_time)
            except Exception as e:
                print(f"❌ Gemini API에서 예상치 못한 에러 발생: {e}")
                return "오류가 발생하여 답변을 생성하지 못했습니다."
        # --- ✨ 재시도 로직 끝 ---

        print(f"❌ {retries}번의 시도 후에도 Gemini API 호출에 실패했습니다.")
        return "오류가 발생하여 답변을 생성하지 못했습니다."

    @staticmethod
    def save_and_upload(content: str, filename: str, drive_folder: str, local_dir: str = "./data/gemini_generated"):
        """생성된 콘텐츠를 로컬에 저장하고 Google Drive에 업로드합니다."""
        os.makedirs(local_dir, exist_ok=True)
        filepath = os.path.join(local_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"📄 Saved locally: {filepath}")

        # GoogleDriveHandler를 사용하여 업로드
        try:
            GoogleDriveHandler.upload_to_drive(filepath, filename, folder_path=drive_folder)
        except Exception as e:
            print(f"❌ Drive upload failed: {e}")
