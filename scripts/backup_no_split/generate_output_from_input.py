import os
import json
import time
import sys
from pathlib import Path
from tqdm import tqdm


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


INPUT_DATA_ROOT = PROJECT_ROOT / 'llm_training_inputs'
RAW_OUTPUT_ROOT = PROJECT_ROOT / 'llm_training_raw_outputs'
sys.path.append(str(SCRIPT_DIR))
from gemini_handler import GeminiHandler


def find_json_files(input_root: Path) -> list:
    """지정된 입력 루트 디렉토리 아래의 모든 .json 파일을 찾습니다."""
    if not input_root.is_dir():
        print(f"🚨 오류: 입력 루트 디렉토리를 찾을 수 없습니다: {input_root}")
        return []
    print(f"🔎 '{input_root}' 디렉토리에서 학습 입력 파일들을 탐색합니다.")
    files_to_process = sorted(list(input_root.rglob("*.json")))
    print(f"✨ 총 {len(files_to_process)}개의 .json 파일을 찾았습니다.")
    return files_to_process


def main():
    """
    최신 Gemini 모델(2.5 Pro)에 최적화된 프롬프트 구조로 API에 요청을 보내고,
    원본 응답을 .txt 파일로 저장하는 메인 함수.
    """

    TARGET_MODEL = "models/gemini-2.5-pro"
    START_INDEX = 1
    END_INDEX = None

    json_files = find_json_files(INPUT_DATA_ROOT)
    if not json_files:
        print("처리할 .json 파일을 찾지 못했습니다. 종료합니다.")
        return

    total_files = len(json_files)
    print(f"\n총 {total_files}개의 .json 파일에 대한 레이블링을 시작합니다.")
    print(f"사용 모델: {TARGET_MODEL}")
    print(f"실행 범위: {START_INDEX}번 파일부터 {END_INDEX or '끝'}번 파일까지")

    for i, file_path in enumerate(tqdm(json_files, desc="파일 처리 진행률"), start=1):
        if i < START_INDEX:
            continue
        if END_INDEX is not None and i > END_INDEX:
            break

        tqdm.write(f"\n--- [{i}/{total_files}] 파일 처리 중: {file_path.name} ---")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                training_data_file = json.load(f)

            instruction = training_data_file.get("instruction")
            input_data = training_data_file.get("input")

            if not instruction or not input_data:
                tqdm.write(f"🚨 오류: {file_path.name}에 'instruction' 또는 'input' 키가 없습니다. 건너뜁니다.")
                continue

            original_stem = file_path.stem.replace('training_input_', '')
            relative_path = file_path.relative_to(INPUT_DATA_ROOT)
            raw_output_dir = RAW_OUTPUT_ROOT / relative_path.parent
            raw_output_filename = f"raw_output_{original_stem}.txt"
            raw_output_file_path = raw_output_dir / raw_output_filename

            if raw_output_file_path.exists():
                tqdm.write(f"⏭️ 건너뛰기: 이미 원본 응답 파일이 존재합니다: {raw_output_file_path.name}")
                continue

            # 사용자 메시지에 명시적인 작업 지시 추가
            user_content = f"""Please analyze the following JSON data based on the instructions provided and generate your response.

# JSON input data to analyze:
```json
{json.dumps(input_data, indent=2, ensure_ascii=False)}
```"""

            # 'system'과 'user' 역할을 엄격히 분리하여 프롬프트 구성
            prompt_for_api = {
                "messages": [
                    {"role": "system", "parts": [instruction]},
                    {"role": "user", "parts": [user_content]}
                ]
            }

            tqdm.write(f"🔹 Gemini로 요청 전송 중...")
            # `gemini_handler`의 `ask` 메서드에 모델 이름을 전달
            api_reply_text = GeminiHandler.ask(prompt_config=prompt_for_api, model_name=TARGET_MODEL)

            raw_output_dir.mkdir(parents=True, exist_ok=True)
            with open(raw_output_file_path, 'w', encoding='utf-8') as f:
                f.write(api_reply_text)

            tqdm.write(f"✅ 처리 성공: 원본 응답 저장 완료 -> {raw_output_filename}")
            tqdm.write(f"--- 파일 처리 완료, 10초 대기 ---")
            time.sleep(10)

        except json.JSONDecodeError:
            tqdm.write(f"🚨 파일이 올바른 JSON 형식이 아닙니다: {file_path.name}")
            continue
        except Exception as e:
            tqdm.write(f"🚨 파일 처리 중 심각한 오류 발생 ({file_path.name}): {e}")
            continue

    print("\n🎉 모든 API 요청 처리가 완료되었습니다.")


if __name__ == "__main__":
    main()