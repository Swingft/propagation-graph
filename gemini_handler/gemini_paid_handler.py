import os
from pathlib import Path
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel
from google_drive_handler import GoogleDriveHandler

# --- 1. Vertex AI 및 환경 변수 설정 ---
load_dotenv()  # .env 파일이 프로젝트 루트에 있다고 가정

PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
LOCATION = os.getenv("GOOGLE_LOCATION")

if not PROJECT_ID or not LOCATION:
    raise ValueError("GOOGLE_PROJECT_ID and GOOGLE_LOCATION must be set in your .env file.")
vertexai.init(project=PROJECT_ID, location=LOCATION)


class GeminiHandler:
    """Vertex AI Gemini API와의 상호작용을 처리하는 핸들러."""

    # 사용할 모델을 클래스 속성으로 정의
    model = GenerativeModel("gemini-1.5-pro-001")

    @classmethod
    def ask(cls, prompt_config):
        """Gemini 모델에 요청을 보내고 텍스트 응답을 반환합니다."""

        # prompt_config가 딕셔너리 형태일 경우, user content만 추출
        if isinstance(prompt_config, dict):
            # 시스템 메시지를 포함한 전체 대화 내용을 전달할 수 있습니다.
            # 여기서는 간단히 user content만 사용합니다.
            user_content = next((msg["content"] for msg in prompt_config.get("messages", []) if msg["role"] == "user"),
                                "")
            # content가 딕셔너리일 경우 task만 추출
            if isinstance(user_content, dict):
                prompt_text = user_content.get("task", "")
            else:
                prompt_text = user_content
        else:  # 단순 문자열일 경우
            prompt_text = prompt_config

        try:
            response = cls.model.generate_content(prompt_text)
            return response.text
        except Exception as e:
            print(f"❌ Gemini API error occurred: {e}")
            return "오류가 발생하여 답변을 생성하지 못했습니다."

    @staticmethod
    def save_and_upload(content: str, filename: str, drive_folder: str, local_dir: str = "./nC1/gemini_generated2"):
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


# --- 아래는 예제 코드입니다 ---
if __name__ == '__main__':
    # 예제 프롬프트
    prompt = "SwiftUI를 사용해서 간단한 'Hello, World!'를 표시하는 코드를 작성해줘."

    # Gemini에게 코드 생성 요청
    generated_code = GeminiHandler.ask(prompt)

    print("\n===== Gemini's Generated Code =====")
    print(generated_code)
    print("=" * 30)

    # 생성된 코드를 파일로 저장하고 드라이브에 업로드
    if "오류가 발생" not in generated_code:
        GeminiHandler.save_and_upload(
            content=generated_code,
            filename="hello_world_gemini.swift",
            drive_folder="gemini_generated_files",  # 업로드할 드라이브 폴더 이름
            local_dir="./generated_code/"
        )