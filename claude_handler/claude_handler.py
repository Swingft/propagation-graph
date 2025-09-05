import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import anthropic

# from google_drive_handler import GoogleDriveHandler

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

dotenv_path = PROJECT_ROOT / '.env'
load_dotenv(dotenv_path=dotenv_path)

sys.path.append(str(SCRIPT_DIR))


class ClaudeHandler:
    """Claude API와의 상호작용을 처리하는 핸들러."""
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise ValueError("CLAUDE_API_KEY가 .env 파일에 설정되지 않았습니다.")
    client = anthropic.Anthropic(api_key=api_key)

    @classmethod
    def ask(cls, prompt_config):
        """Claude 모델에 요청을 보내고 응답을 반환합니다."""
        if isinstance(prompt_config, dict):
            system_prompt = next(
                (msg["content"] for msg in prompt_config.get("messages", []) if msg["role"] == "system"), None)
            user_messages = [msg for msg in prompt_config.get("messages", []) if msg["role"] != "system"]

            params = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "messages": user_messages
            }
            if system_prompt:
                params["system"] = system_prompt

            response = cls.client.messages.create(**params)
        else:
            response = cls.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt_config}]
            )

        return response.content[0].text.strip()

    @staticmethod
    def save_and_upload(content: str, filename: str, drive_folder: str, local_dir: str):
        """
        생성된 콘텐츠를 로컬에 저장하고 Google Drive에 업로드합니다.
        """
        os.makedirs(local_dir, exist_ok=True)
        filepath = os.path.join(local_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"📄 Saved locally: {filepath}")

        # 공용 GoogleDriveHandler를 사용하여 업로드
        # try:
        #     GoogleDriveHandler.upload_to_drive(filepath, filename, folder_path=drive_folder)
        # except Exception as e:
        #     print(f"❌ Drive upload failed: {e}")
