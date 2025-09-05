import os
import sys
import time
import json
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions
from google.generativeai.types import HarmCategory, HarmBlockThreshold

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

dotenv_path = PROJECT_ROOT / '.env'
load_dotenv(dotenv_path=dotenv_path)

sys.path.append(str(SCRIPT_DIR))

# --- API 키 로드 ---
API_KEY_NAMES = [
    "GEMINI_API_KEY_KS", "GEMINI_API_KEY_DH", "GEMINI_API_KEY_GN", "GEMINI_API_KEY_HJ",
    "GEMINI_API_KEY_SH", "GEMINI_API_KEY_SI", "GEMINI_API_KEY_BW", "GEMINI_API_KEY_SW",
]
API_KEYS = [os.getenv(key_name) for key_name in API_KEY_NAMES if os.getenv(key_name)]
if not API_KEYS:
    raise ValueError("하나 이상의 GEMINI_API_KEY가 .env 파일에 설정되어야 합니다.")


# --- 커스텀 에러 정의 ---
class GeminiResponseEmptyError(RuntimeError):
    """Gemini API가 비어있는 응답을 반환했을 때 발생하는 에러"""
    pass


class GeminiBlockedError(RuntimeError):
    """Gemini API가 안전 설정 또는 기타 사유로 콘텐츠를 차단했을 때 발생하는 에러"""
    pass


class GeminiHandler:
    """Gemini API와의 상호작용, 재시도, 키 전환을 처리하는 핸들러."""
    api_keys = API_KEYS
    current_key_index = 0

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    generation_config = {
        "temperature": 0.2,
        "max_output_tokens": 8192,
    }

    @classmethod
    def _get_configured_model(cls, system_instruction: str | None = None):
        if cls.current_key_index >= len(cls.api_keys):
            raise RuntimeError("사용 가능한 모든 Gemini API 키가 소진되었습니다.")

        current_key = cls.api_keys[cls.current_key_index]
        genai.configure(api_key=current_key)

        return genai.GenerativeModel(
            "gemini-2.5-pro",
            safety_settings=cls.safety_settings,
            generation_config=cls.generation_config,
            system_instruction=system_instruction
        )

    @classmethod
    def ask(cls, prompt_config: dict, retries: int = 3, base_wait: int = 5) -> str:
        messages = prompt_config.get("messages")
        if not messages:
            raise ValueError("프롬프트 설정에 'messages' 키가 없거나 비어있습니다.")

        system_prompt = next((msg.get("parts", [""])[0] for msg in messages if msg["role"] == "system"), None)
        user_messages = [msg for msg in messages if msg["role"] != "system"]

        last_err = None
        for attempt in range(1, retries + 1):
            try:
                print(f"🔑 Gemini API 키 #{cls.current_key_index + 1}로 요청 시도...")
                model = cls._get_configured_model(system_instruction=system_prompt)

                resp = model.generate_content(
                    user_messages,
                    request_options={"timeout": 120}
                )

                # [오류 수정] response.text를 직접 호출하기 전에 응답 유효성을 먼저 검사합니다.
                if not resp.candidates:
                    # 후보가 아예 없는 경우 (안전 설정 등으로 완전히 차단된 경우)
                    block_reason = "Unknown"
                    if hasattr(resp, 'prompt_feedback') and resp.prompt_feedback.block_reason:
                        block_reason = resp.prompt_feedback.block_reason.name
                    raise GeminiBlockedError(f"응답이 차단됨 (No candidates returned). Block Reason: {block_reason}")

                candidate = resp.candidates[0]

                # RECITATION(finish_reason=2) 등 텍스트가 없는 경우를 명시적으로 처리
                if not candidate.content or not candidate.content.parts:
                    raise GeminiBlockedError(f"콘텐츠가 없음 (finish_reason={candidate.finish_reason.name})")

                text = candidate.content.parts[0].text

                if not text or not text.strip():
                    raise GeminiResponseEmptyError(f"빈 텍스트 응답 (finish_reason={candidate.finish_reason.name})")

                return text.strip()

            except exceptions.ResourceExhausted as e:
                print(f"  ⚠️ Gemini API 키 #{cls.current_key_index + 1}의 사용량 한도 도달. 키 전환 시도...")
                cls.current_key_index += 1
                if cls.current_key_index < len(cls.api_keys):
                    last_err = e
                    continue
                else:
                    raise RuntimeError(f"모든 Gemini API 키의 사용량 한도에 도달했습니다. 마지막 오류: {e}")

            except (GeminiResponseEmptyError, GeminiBlockedError) as e:
                wait = base_wait * (2 ** (attempt - 1))
                print(f"  ⚠️ 비어 있거나 차단된 응답. {wait}초 후 재시도... ({attempt}/{retries}) :: {e}")
                time.sleep(wait)
                last_err = e

            except exceptions.DeadlineExceeded as e:
                wait = base_wait * (2 ** (attempt - 1))
                print(f"  ⚠️ API 요청 시간 초과. {wait}초 후 재시도... ({attempt}/{retries})")
                time.sleep(wait)
                last_err = e

            except Exception as e:
                wait = base_wait * (2 ** (attempt - 1))
                error_summary = str(e).split('\n')[0]
                print(f"  ⚠️ 예상치 못한 오류. {wait}초 후 재시도... ({attempt}/{retries}) :: {error_summary}")
                time.sleep(wait)
                last_err = e

        raise RuntimeError(f"Gemini가 {retries}번의 재시도 후 실패했습니다: {last_err}")

    @staticmethod
    def save_content(content: str, output_path: str):
        """제공된 내용을 파일에 저장합니다."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)

