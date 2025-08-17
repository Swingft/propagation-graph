# gemini_handler.py
import os
import time
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions
from google.generativeai.types import HarmCategory, HarmBlockThreshold

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY_DH")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY must be set in your .env file.")
genai.configure(api_key=API_KEY)


class GeminiResponseEmptyError(RuntimeError):
    pass


class GeminiBlockedError(RuntimeError):
    pass


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
    def ask(cls, prompt_config, retries: int = 3, base_wait: int = 5) -> str:
        """
        Gemini에 요청을 보내고 '정상 텍스트'가 있을 때만 문자열을 반환.
        - 실패 시: 예외를 던짐 (저장/업로드 금지)
        - 재시도 정책:
            * ResourceExhausted(쿼터/속도 제한): 61초 대기 후 재시도
            * 기타 오류/빈 응답/블록: 지수 백오프(5s, 10s, 20s ...)
        """
        if isinstance(prompt_config, dict):
            user_message = next(
                (m for m in prompt_config.get("messages", []) if m.get("role") == "user"),
                None,
            )
            prompt_text = user_message["content"] if user_message else ""
        else:
            prompt_text = prompt_config

        last_err = None
        for attempt in range(1, retries + 1):
            try:
                resp = cls.model.generate_content(prompt_text)

                # ---- 유효성 검사 ----
                # 1) 응답 텍스트가 비었는지
                text = getattr(resp, "text", None)
                if not text or not text.strip():
                    # finish_reason이 STOP이 아니거나 candidates가 비었을 수 있음
                    # prompt_feedback이 block인 경우도 있음
                    # block 여부를 최대한 감지
                    pf = getattr(resp, "prompt_feedback", None)
                    if pf and getattr(pf, "block_reason", None) not in (None, 0, "BLOCK_REASON_UNSPECIFIED"):
                        raise GeminiBlockedError(f"Blocked by safety: {pf.block_reason}")
                    # candidates 존재 여부도 점검
                    cands = getattr(resp, "candidates", None)
                    fr = None
                    if cands:
                        fr = getattr(cands[0], "finish_reason", None)
                    raise GeminiResponseEmptyError(f"Empty response (finish_reason={fr})")

                return text  # ✅ 성공 시에만 문자열 반환

            except exceptions.ResourceExhausted as e:
                # 분당/일일 제한 등: 61초 대기 후 재시도
                wait = 61
                print(f"  ⚠️ Rate limit/quota hit. Retry in {wait}s... ({attempt}/{retries})")
                time.sleep(wait)
                last_err = e
            except (GeminiResponseEmptyError, GeminiBlockedError) as e:
                # 텍스트 없음/블록: 점진적 백오프
                wait = base_wait * (2 ** (attempt - 1))
                print(f"  ⚠️ Empty/Blocked response. Retry in {wait}s... ({attempt}/{retries}) :: {e}")
                time.sleep(wait)
                last_err = e
            except Exception as e:
                # 기타 오류: 점진적 백오프
                wait = base_wait * (2 ** (attempt - 1))
                print(f"  ⚠️ Unexpected error. Retry in {wait}s... ({attempt}/{retries}) :: {e}")
                time.sleep(wait)
                last_err = e

        # 모든 재시도 실패 시 예외
        raise RuntimeError(f"Gemini failed after {retries} retries: {last_err}")


    @staticmethod
    def save_and_upload(content: str, filename: str, drive_folder: str, local_dir: str = "./data/gemini_generated"):
        """
        ✅ 성공 시에만 호출해야 함!
        생성된 콘텐츠를 로컬에 저장하고, Google Drive에 업로드.
        """
        from google_drive_handler import GoogleDriveHandler  # 지연 임포트(실패 시 불필요한 의존 회피)

        os.makedirs(local_dir, exist_ok=True)
        filepath = os.path.join(local_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"📄 Saved locally: {filepath}")

        try:
            GoogleDriveHandler.upload_to_drive(filepath, filename, folder_path=drive_folder)
        except Exception as e:
            print(f"❌ Drive upload failed: {e}")
