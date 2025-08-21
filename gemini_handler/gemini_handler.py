import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from google_drive_handler import GoogleDriveHandler


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

dotenv_path = PROJECT_ROOT / '.env'
load_dotenv(dotenv_path=dotenv_path)

sys.path.append(str(SCRIPT_DIR))


API_KEY_NAMES = [
    "GEMINI_API_KEY_DH", "GEMINI_API_KEY_GN", "GEMINI_API_KEY_HJ",
    "GEMINI_API_KEY_SH", "GEMINI_API_KEY_SI",
]
API_KEYS = [os.getenv(key_name) for key_name in API_KEY_NAMES if os.getenv(key_name)]
if not API_KEYS:
    raise ValueError("하나 이상의 GEMINI_API_KEY가 .env 파일에 설정되어야 합니다.")


class GeminiResponseEmptyError(RuntimeError):
    pass


class GeminiBlockedError(RuntimeError):
    pass


class GeminiHandler:
    api_keys = API_KEYS
    current_key_index = 0
    model = None

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    @classmethod
    def _configure_genai(cls):
        """현재 인덱스에 맞는 API 키로 genai와 모델을 설정합니다."""
        if cls.current_key_index >= len(cls.api_keys):
            raise RuntimeError("사용 가능한 모든 Gemini API 키가 소진되었습니다.")

        current_key = cls.api_keys[cls.current_key_index]
        print(f"🔑 Gemini API 키 #{cls.current_key_index + 1}로 설정 중...")
        genai.configure(api_key=current_key)
        cls.model = genai.GenerativeModel("gemini-2.5-flash", safety_settings=cls.safety_settings)

    @classmethod
    def ask(cls, prompt_config, retries: int = 3, base_wait: int = 5) -> str:
        if cls.model is None:
            cls._configure_genai()

        prompt_text = prompt_config if isinstance(prompt_config, str) else ""
        if isinstance(prompt_config, dict):
            user_message = next((m for m in prompt_config.get("messages", []) if m.get("role") == "user"), None)
            prompt_text = user_message["content"] if user_message else ""

        last_err = None
        for attempt in range(1, retries + 1):
            try:
                resp = cls.model.generate_content(prompt_text)
                text = getattr(resp, "text", None)
                if not text or not text.strip():
                    pf = getattr(resp, "prompt_feedback", None)
                    if pf and getattr(pf, "block_reason", None) not in (None, 0, "BLOCK_REASON_UNSPECIFIED"):
                        raise GeminiBlockedError(f"안전 설정에 의해 차단됨: {pf.block_reason}")
                    cands = getattr(resp, "candidates", None)
                    fr = getattr(cands[0], "finish_reason", None) if cands else None
                    raise GeminiResponseEmptyError(f"빈 응답 (finish_reason={fr})")
                return text

            except exceptions.ResourceExhausted as e:
                print(f"  ⚠️ Gemini API 키 #{cls.current_key_index + 1}의 사용량 한도 도달. 키 전환 시도...")
                cls.current_key_index += 1
                if cls.current_key_index < len(cls.api_keys):
                    cls._configure_genai()
                    last_err = e
                    continue
                else:
                    error_summary = str(e).split('\n')[0]
                    raise RuntimeError(f"모든 Gemini API 키의 사용량 한도에 도달했습니다. 마지막 오류: {error_summary}")

            except (GeminiResponseEmptyError, GeminiBlockedError) as e:
                wait = base_wait * (2 ** (attempt - 1))
                print(f"  ⚠️ 비어 있거나 차단된 응답. {wait}초 후 재시도... ({attempt}/{retries}) :: {e}")
                time.sleep(wait)
                last_err = e
            except Exception as e:
                wait = base_wait * (2 ** (attempt - 1))
                print(f"  ⚠️ 예상치 못한 오류. {wait}초 후 재시도... ({attempt}/{retries}) :: {e}")
                time.sleep(wait)
                last_err = e

        raise RuntimeError(f"Gemini가 {retries}번의 재시도 후 실패했습니다: {last_err}")

    @staticmethod
    def save_and_upload(content: str, filename: str, drive_folder: str, local_dir: str):
        """
        생성된 콘텐츠를 로컬에 저장하고 Google Drive에 업로드합니다.
        """
        os.makedirs(local_dir, exist_ok=True)
        filepath = os.path.join(local_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"📄 로컬에 저장됨: {filepath}")

        try:
            GoogleDriveHandler.upload_to_drive(filepath, filename, folder_path=drive_folder)
        except Exception as e:
            print(f"❌ Drive 업로드 실패: {e}")


GeminiHandler._configure_genai()
