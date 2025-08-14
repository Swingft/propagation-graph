import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from google_drive_handler import GoogleDriveHandler

load_dotenv()


class GPTHandler:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @classmethod
    def ask(cls, prompt_config):
        """GPT 모델에 요청을 보내고 응답을 반환합니다."""
        # prompt_config가 딕셔너리 형태일 경우를 대비
        if isinstance(prompt_config, dict):
            messages = prompt_config.get("messages", [])
        else:  # 단순 문자열일 경우
            messages = [{"role": "user", "content": prompt_config}]

        response = cls.client.chat.completions.create(
            model="gpt-4o",  # 모델 이름은 필요에 따라 변경
            messages=messages
        )
        return response.choices[0].message.content.strip()

    @staticmethod
    def save_and_upload(code: str, filename: str, drive_folder: str, local_dir: str = "./data/gpt_generated"):
        """생성된 코드를 로컬에 저장하고 Google Drive에 업로드합니다."""
        os.makedirs(local_dir, exist_ok=True)
        filepath = os.path.join(local_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"📄 Saved locally: {filepath}")

        # GoogleDriveHandler를 사용하여 업로드
        try:
            GoogleDriveHandler.upload_to_drive(filepath, filename, folder_path=drive_folder)
        except Exception as e:
            print(f"❌ Drive upload failed: {e}")