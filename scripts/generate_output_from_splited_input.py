import os
import sys
import time
import json
from pathlib import Path
from tqdm import tqdm
from gemini_handler import GeminiHandler


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

INPUT_DATA_ROOT = PROJECT_ROOT / 'llm_training_data_split' / 'inputs'
RAW_OUTPUT_ROOT = PROJECT_ROOT / 'llm_training_data_split' / 'outputs'

sys.path.append(str(SCRIPT_DIR))


def find_json_files(input_root: Path) -> list:
    """지정된 입력 루트 디렉토리 아래의 모든 .json 파일을 재귀적으로 찾습니다."""
    if not input_root.is_dir():
        print(f"🚨 오류: 입력 루트 디렉토리를 찾을 수 없습니다: {input_root}")
        return []
    print(f"🔎 '{input_root}' 디렉토리에서 분할된 입력 파일들을 탐색합니다.")
    # rglob를 사용하여 모든 하위 디렉토리의 파일을 찾습니다.
    files_to_process = sorted(list(input_root.rglob("*.json")))
    print(f"✨ 총 {len(files_to_process)}개의 파일을 찾았습니다.")
    return files_to_process


def main():
    """
    분할된 각 .json 파일을 API에 요청으로 보내고,
    원본 응답을 .txt 파일로 저장하는 메인 함수.
    """

    TARGET_MODEL = "models/gemini-2.5-pro"
    START_INDEX = 486
    END_INDEX = None

    RAW_OUTPUT_ROOT.mkdir(exist_ok=True)
    json_files = find_json_files(INPUT_DATA_ROOT)
    if not json_files:
        print("처리할 .json 파일을 찾지 못했습니다. 종료합니다.")
        return

    total_files = len(json_files)
    print(f"\n총 {total_files}개의 분할된 파일에 대한 레이블링을 시작합니다.")
    print(f"사용 모델: {TARGET_MODEL}")
    print(f"실행 범위: {START_INDEX}번 파일부터 {END_INDEX or '끝'}번 파일까지")

    for i, file_path in enumerate(tqdm(json_files, desc="분할 파일 처리 진행률"), start=1):
        if i < START_INDEX:
            continue
        if END_INDEX is not None and i > END_INDEX:
            break

        tqdm.write(f"\n--- [{i}/{total_files}] 파일 처리 중: {file_path.relative_to(PROJECT_ROOT)} ---")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                training_data_file = json.load(f)

            instruction = training_data_file.get("instruction")
            input_data = training_data_file.get("input")

            if not instruction or not input_data:
                tqdm.write(f"🚨 오류: {file_path.name}에 'instruction' 또는 'input' 키가 없습니다. 건너뜁니다.")
                continue

            # 출력 파일 경로를 입력 구조와 동일하게 설정.
            relative_path = file_path.relative_to(INPUT_DATA_ROOT)
            output_dir = RAW_OUTPUT_ROOT / relative_path.parent
            original_stem = file_path.stem.replace('input_', '')
            # 저장 형식을 .json으로 변경하여 최종 데이터와 일관성을 맞춤.
            output_filename = f"output_{original_stem}.json"
            output_file_path = output_dir / output_filename

            if output_file_path.exists():
                tqdm.write(f"⏭️ 건너뛰기: 이미 결과 파일이 존재합니다: {output_file_path.name}")
                continue

            user_content = f"""Please analyze the following JSON data based on the instructions provided and generate your response.

# JSON input data to analyze:
```json
{json.dumps(input_data, indent=2, ensure_ascii=False)}
```"""

            prompt_for_api = {
                "messages": [
                    {"role": "system", "parts": [instruction]},
                    {"role": "user", "parts": [user_content]}
                ]
            }

            tqdm.write(f"🔹 Gemini로 요청 전송 중...")
            api_reply_text = GeminiHandler.ask(prompt_config=prompt_for_api, model_name=TARGET_MODEL)

            output_dir.mkdir(parents=True, exist_ok=True)
            # API 응답을 그대로 텍스트로 저장.
            with open(output_file_path, 'w', encoding='utf-8') as f:
                # API 응답이 JSON 형식을 보장하지 않으므로, 텍스트 그대로 저장.
                # 다음 단계에서 파싱 및 검증
                f.write(api_reply_text)

            tqdm.write(f"✅ 처리 성공: 결과 저장 완료 -> {output_filename}")

            wait_time = 10
            tqdm.write(f"--- 파일 처리 완료, {wait_time}초 대기 ---")
            time.sleep(wait_time)

        except json.JSONDecodeError:
            tqdm.write(f"🚨 파일이 올바른 JSON 형식이 아닙니다: {file_path.name}")
            continue
        except Exception as e:
            tqdm.write(f"🚨 파일 처리 중 심각한 오류 발생 ({file_path.name}): {e}")
            continue

    print("\n🎉 모든 API 요청 처리가 완료되었습니다.")


if __name__ == "__main__":
    main()

