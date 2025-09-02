import os
import sys
import time
import json
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- 스크립트 경로 및 .env 파일 설정 ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# .env 파일이 존재할 경우 로드
dotenv_path = PROJECT_ROOT / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
else:
    # 예시: 스크립트와 동일한 위치에 .env가 있는 경우
    dotenv_path = SCRIPT_DIR / '.env'
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)

sys.path.append(str(SCRIPT_DIR))

# --- API 키 로드 ---
API_KEY_NAMES = [
    "GEMINI_API_KEY_KS", "GEMINI_API_KEY_DH", "GEMINI_API_KEY_GN", "GEMINI_API_KEY_HJ",
    "GEMINI_API_KEY_SH", "GEMINI_API_KEY_SI", "GEMINI_API_KEY_BW", "GEMINI_API_KEY_SW",
    "GEMINI_API_KEY"
]
API_KEYS = [os.getenv(key_name) for key_name in API_KEY_NAMES if os.getenv(key_name)]
if not API_KEYS:
    raise ValueError("하나 이상의 GEMINI_API_KEY가 .env 파일에 설정되어야 합니다.")


# --- 커스텀 에러 정의 ---
class GeminiResponseEmptyError(RuntimeError):
    """Gemini API가 비어있는 응답을 반환했을 때 발생하는 에러"""
    pass


class GeminiBlockedError(RuntimeError):
    """Gemini API가 안전 설정에 의해 콘텐츠를 차단했을 때 발생하는 에러"""
    pass


# --- Gemini API 핸들러 클래스 ---
class GeminiHandler:
    api_keys = API_KEYS
    current_key_index = 0
    model = None

    # 📝 안전 설정: 모든 카테고리에 대해 제한 없이 허용
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    # ✨ [개선] 더 안정적이고 일관된 JSON 분석 결과를 위한 추천 파라미터 설정
    generation_config = {
        "temperature": 0.1,
        "top_k": 40,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
    }


    @classmethod
    def _configure_genai(cls):
        """현재 인덱스에 맞는 API 키로 genai와 모델을 설정합니다."""
        if cls.current_key_index >= len(cls.api_keys):
            raise RuntimeError("사용 가능한 모든 Gemini API 키가 소진되었습니다.")

        current_key = cls.api_keys[cls.current_key_index]
        print(f"🔑 Gemini API 키 #{cls.current_key_index + 1}로 설정 중...")
        genai.configure(api_key=current_key)

        # ✨ [수정] 요청하신 "gemini-2.5-pro" 모델명으로 변경
        cls.model = genai.GenerativeModel(
            "gemini-2.5-pro",
            safety_settings=cls.safety_settings,
            generation_config=cls.generation_config
        )

    @classmethod
    def ask(cls, prompt_config: dict, retries: int = 3, base_wait: int = 5) -> str:
        """
        구조화된 프롬프트를 사용하여 Gemini API에 질문하고 응답을 받습니다.
        """
        if cls.model is None:
            cls._configure_genai()

        messages = prompt_config.get("messages")
        if not messages:
            raise ValueError("프롬프트 설정에 'messages' 키가 비어있습니다.")

        last_err = None
        for attempt in range(1, retries + 1):
            try:
                resp = cls.model.generate_content(messages)
                text = getattr(resp, "text", None)

                if not text or not text.strip():
                    pf = getattr(resp, "prompt_feedback", None)
                    if pf and getattr(pf, "block_reason", None) not in (None, 0, "BLOCK_REASON_UNSPECIFIED"):
                        raise GeminiBlockedError(f"안전 설정에 의해 차단됨: {pf.block_reason}")

                    cands = getattr(resp, "candidates", None)
                    fr = getattr(cands[0], "finish_reason", None) if cands else "UNKNOWN"
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
    def save_content(content: str, filename: str, local_dir: str = "output"):
        """생성된 콘텐츠를 로컬에 저장합니다."""
        os.makedirs(local_dir, exist_ok=True)
        filepath = os.path.join(local_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"📄 로컬에 저장됨: {filepath}")


# --- 메인 실행 블록 (사용 예시) ---
if __name__ == "__main__":
    instruction_text = """Your Role: You are an expert static analysis assistant with a deep understanding of Swift's semantic structure. Your mission is to meticulously analyze the provided symbol information to identify which symbols must have their names preserved during code obfuscation and to clearly justify your reasoning.

Input Data:
The input is a JSON object containing symbol information generated by analyzing Swift source code. Each symbol includes a `symbol_id`, a `symbol_name`, and an `input` field containing the data for analysis.

Procedure:
1.  **Symbol-by-Symbol Analysis**: For every symbol provided, thoroughly examine the data within its `input` field.
2.  **Identify Exclusions**: Identify symbols that must be excluded from obfuscation based on clear evidence matching one or more of the **'Core Analysis Patterns'** below.
3.  **Generate Output**: For the identified exclusion candidates only, generate a result conforming to the **'Output Format'** rules. Symbols that can be safely obfuscated should not be included in the final output.

Core Analysis Patterns (Decision Criteria):
-   **Runtime String References** (`objc_selector`, `stringly_typed_api`)
-   **KVC/KVO and Data Binding** (`kvc_kvo`, `coredata_nsmanaged`)
-   **C Function Interface (FFI) Exposure** (`ffi_entry`)
-   **Reflection** (`runtime_reflection`)
-   **Codable Synthesis** (`codable_synthesis`)
-   **Resource Binding** (`resource_binding`)
-   **External Contracts and Extensions** (`external_contract`)
-   **Dynamic Dispatch & ObjC Exposure** (`dynamic_dispatch`, `objc_exposed`)
-   **Protocol Requirement Implementation** (`protocol_requirement`)

Output Format:
The result is a JSON object containing **only the symbols that must be excluded from obfuscation**. Each symbol must consist of the following fields:

-   `symbol_name`: The pure name **excluding function arguments**.
-   `tags`: An array of standard tags corresponding to the reason for exclusion.
-   `rationale`: A clear, 1-2 sentence explanation for the exclusion, based on the `input` data.
"""

    example_output_text = """{
  "methods": [
    {
      "symbol_name": "updateConfiguration",
      "tags": [
        "kvo"
      ],
      "rationale": "This method is declared '@objc dynamic' and can be a target for KVO (Key-Value Observing), requiring its name to be preserved."
    }
  ],
  "properties": [],
  "structs": [],
  "enums": []
}
"""

    user_input_data = {
        "mapping": {"is_protocol_requirement_impl": "p1", "codable_synthesized": "p2", "access_level": "p3",
                    "is_ffi_entry": "p4", "override_depth": "p5", "modifiers": "p6", "is_coredata_nsmanaged": "p7",
                    "ast_path": "p8", "cross_module_refs": "p9", "is_objc_exposed": "p10", "type_signature": "p11",
                    "extension_file_count_same_name": "p12", "is_swiftdata_model": "p13", "symbol_kind": "p14",
                    "references": "p15", "calls_out": "p16", "selector_refs": "p17", "attributes": "p18",
                    "extension_of": "p19", "inherits": "p20", "conforms": "p21"},
        "symbols": [{"input": {"p1": False, "p2": False, "p3": "internal", "p4": False, "p5": 0, "p7": False,
                               "p8": ["SourceFile", "EnumDecl"], "p9": False, "p10": False,
                               "p21": ["String", "CodingKey"], "p11": "", "p12": 0, "p13": False, "p14": "enum"},
                     "symbol_name": "CodingKeys", "category": "enums"}, {
                        "input": {"p1": False, "p2": False, "p3": "internal", "p4": False, "p5": 0, "p7": False,
                                  "p8": ["SourceFile", "EnumCaseDecl"], "p9": False, "p10": False, "p11": "", "p12": 0,
                                  "p13": False, "p14": "enumCase"}, "symbol_name": ".isPremium",
                        "category": "enumCases"}]
    }

    prompt = {
        "messages": [
            {'role': 'user', 'parts': [instruction_text]},
            {'role': 'model', 'parts': [example_output_text]},
            {'role': 'user', 'parts': [json.dumps(user_input_data)]}
        ]
    }

    try:
        GeminiHandler._configure_genai()

        print("\n🚀 Gemini에게 분석을 요청합니다...")
        result_text = GeminiHandler.ask(prompt)

        print("\n✅ 분석 완료! 결과:\n")
        try:
            parsed_json = json.loads(result_text)
            print(json.dumps(parsed_json, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(result_text)

        GeminiHandler.save_content(result_text, "analysis_result.json")

    except Exception as e:
        print(f"\n❌ 스크립트 실행 중 오류가 발생했습니다: {e}")

