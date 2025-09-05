import os
import json
import time
import sys
from pathlib import Path
from tqdm import tqdm

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# 1. 원본 학습 입력 데이터가 있는 곳
INPUT_DATA_ROOT = PROJECT_ROOT / 'llm_training_inputs'
# 2. Gemini의 원본 응답을 백업할 곳 (중간 결과물)
RAW_OUTPUT_ROOT = PROJECT_ROOT / 'llm_training_raw_outputs'

sys.path.append(str(SCRIPT_DIR))

# from claude_handler import ClaudeHandler
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
    .json 파일을 API에 요청으로 보내고, 원본 응답을 .txt 파일로 저장하는 메인 함수.
    이 스크립트는 시간이 오래 걸리는 API 호출만 담당합니다.
    """
    START_INDEX = 1
    END_INDEX = None

    json_files = find_json_files(INPUT_DATA_ROOT)
    if not json_files:
        print("처리할 .json 파일을 찾지 못했습니다. 종료합니다.")
        return

    total_files = len(json_files)
    print(f"\n총 {total_files}개의 .json 파일에 대한 레이블링을 시작합니다.")
    print(f"실행 범위: {START_INDEX}번 파일부터 {END_INDEX or '끝'}번 파일까지")

    for i, file_path in enumerate(json_files, start=1):
        if i < START_INDEX:
            continue
        if END_INDEX is not None and i > END_INDEX:
            break

        print(f"\n--- [{i}/{total_files}] 파일 처리 중: {file_path.name} ---")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                training_data_file = json.load(f)

            instruction = training_data_file.get("instruction")
            input_data = training_data_file.get("input")

            if not instruction or not input_data:
                print(f"🚨 오류: {file_path.name} 파일에 'instruction' 또는 'input' 키가 없습니다. 건너뜁니다.")
                continue

            original_stem = file_path.stem.replace('training_input_', '')

            # 원본 응답을 저장할 파일 경로
            relative_path = file_path.relative_to(INPUT_DATA_ROOT)
            raw_output_dir = RAW_OUTPUT_ROOT / relative_path.parent
            raw_output_filename = f"raw_output_{original_stem}.txt"
            raw_output_file_path = raw_output_dir / raw_output_filename

            # 중간에 끊었다가 다시 시작할 수 있도록 이미 처리된 파일은 건너뜀
            if raw_output_file_path.exists():
                print(f"⏭️ 건너뛰기: 이미 원본 응답 파일이 존재합니다: {raw_output_file_path.name}")
                continue

            full_prompt = f"""{instruction}

# JSON input data to analyze:
```json
{json.dumps(input_data, indent=2, ensure_ascii=False)}
```"""

            prompt_for_api = {
                "messages": [{"role": "user", "parts": [full_prompt]}]
            }

            print(f"🔹 Gemini로 요청 전송 중...")
            api_reply_text = GeminiHandler.ask(prompt_for_api)

            # 성공한 경우에만 응답을 저장.
            raw_output_dir.mkdir(parents=True, exist_ok=True)
            with open(raw_output_file_path, 'w', encoding='utf-8') as f:
                f.write(api_reply_text)

            print(f"✅ 처리 성공: 원본 응답 저장 완료 -> {raw_output_filename}")

            print(f"--- 파일 처리 완료, 10초 대기 ---")
            time.sleep(10)

        except json.JSONDecodeError:
            print(f"🚨 파일이 올바른 JSON 형식이 아닙니다. 건너뜁니다: {file_path.name}")
            continue
        except Exception as e:
            print(f"🚨 파일 처리 중 심각한 오류 발생 ({file_path.name}): {e}")
            print("   자세한 내용은 GeminiHandler에서 출력된 API 응답 로그를 확인하세요.")
            continue

    print("\n🎉 모든 API 요청 처리가 완료되었습니다.")


if __name__ == "__main__":
    main()

