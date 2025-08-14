# claude_handler.py
import os
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from google_drive_handler import GoogleDriveHandler

load_dotenv()


class ClaudeHandler:
    """Claude API와의 상호작용을 처리하는 핸들러."""
    client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

    @classmethod
    def ask(cls, prompt_config):
        """Claude 모델에 요청을 보내고 응답을 반환합니다."""
        # 딕셔너리 또는 문자열 형태의 프롬프트를 처리하는 로직
        if isinstance(prompt_config, dict):
            system_prompt = next(
                (msg["content"] for msg in prompt_config.get("messages", []) if msg["role"] == "system"), None)
            user_messages = [msg for msg in prompt_config.get("messages", []) if msg["role"] != "system"]

            params = {
                "model": "claude-3-5-sonnet-20240620",
                "max_tokens": 4096,
                "messages": user_messages
            }
            if system_prompt:
                params["system"] = system_prompt

            response = cls.client.messages.create(**params)
        else:
            response = cls.client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt_config}]
            )

        return response.content[0].text.strip()

    @staticmethod
    def save_and_upload(content: str, filename: str, drive_folder: str, local_dir: str = "./data/claude_generated"):
        """
        생성된 Swift 코드를 로컬에 저장하고 Google Drive에 업로드합니다.
        (GPT/Gemini 핸들러와 완전히 동일한 구조)
        """
        os.makedirs(local_dir, exist_ok=True)
        filepath = os.path.join(local_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"📄 Saved locally: {filepath}")

        # 공용 GoogleDriveHandler를 사용하여 업로드
        try:
            GoogleDriveHandler.upload_to_drive(filepath, filename, folder_path=drive_folder)
        except Exception as e:
            print(f"❌ Drive upload failed: {e}")