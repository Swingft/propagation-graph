import os
import json
import time
import sys
from pathlib import Path

# from claude_handler import ClaudeHandler
from gemini_handler import GeminiHandler

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

INPUT_ROOT = PROJECT_ROOT / 'input_label'
OUTPUT_ROOT = PROJECT_ROOT / 'output_label'

sys.path.append(str(SCRIPT_DIR))


def find_json_files(input_root: Path) -> list:
    """
    지정된 입력 루트 디렉토리 아래의 모든 프로젝트 폴더에서 .json 파일을 찾습니다.
    'jsonl_format' 하위 디렉토리는 제외합니다.
    """
    files_to_process = []
    if not input_root.is_dir():
        print(f"🚨 오류: 입력 루트 디렉토리를 찾을 수 없습니다: {input_root}")
        return []

    # input_root 바로 아래에 있는 모든 하위 폴더를 프로젝트로 간주하고 탐색합니다.
    project_folders = [d for d in input_root.iterdir() if d.is_dir()]
    print(f"🔎 총 {len(project_folders)}개의 프로젝트 폴더를 탐색합니다.")

    for project_folder in project_folders:
        print(f"   - '{project_folder.name}' 처리 중...")
        for root, dirs, files in os.walk(project_folder):
            # 'jsonl_format' 폴더는 탐색에서 제외
            if 'jsonl_format' in dirs:
                dirs.remove('jsonl_format')

            for filename in files:
                if filename.endswith('.json'):
                    files_to_process.append(os.path.join(root, filename))

    files_to_process.sort()
    return files_to_process


def main():
    """
    .json 파일을 API에 요청으로 보내고, 결과를 저장 및 업로드하는 메인 함수.
    """
    # 4803
    START_INDEX = 1
    END_INDEX = None

    json_files = find_json_files(INPUT_ROOT)
    if not json_files:
        print("처리할 .json 파일을 찾지 못했습니다. 종료합니다.")
        return

    total_files = len(json_files)
    print(f"\n총 {total_files}개의 .json 파일을 처리합니다.")
    print(f"실행 범위: {START_INDEX}번 파일부터 {END_INDEX or '끝'}번 파일까지")

    for i, file_path_str in enumerate(json_files, start=1):
        if i < START_INDEX:
            continue
        if END_INDEX is not None and i > END_INDEX:
            print(f"\n--- 종료 인dex({END_INDEX})에 도달하여 처리를 중단합니다. ---")
            break

        file_path = Path(file_path_str)
        filename_base = file_path.name
        print(f"\n--- [{i}/{total_files}] 파일 처리 중: {filename_base} ---")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                request_payload = json.load(f)

            data_payload = request_payload.get("data", {})
            prompt_instructions = data_payload.get("meta", {}).get("prompt_context", "")
            symbol_data_to_process = data_payload.get("decisions", {})

            if not prompt_instructions or not symbol_data_to_process:
                print(f"🚨 오류: {filename_base} 파일의 'data' 객체 안에 'meta.prompt_context' 또는 'decisions' 데이터가 없습니다. 건너뜁니다.")
                continue

            original_filename_no_ext = file_path.stem
            output_filename = f"output_{original_filename_no_ext.replace('input_', '')}.json"

            relative_path = file_path.relative_to(INPUT_ROOT)
            output_dir = OUTPUT_ROOT / relative_path.parent
            output_file_path = output_dir / output_filename

            full_prompt = f"""{prompt_instructions}

# JSON data to analyze:
```json
{json.dumps(symbol_data_to_process, indent=2, ensure_ascii=False)}
```

[CRITICAL] Final Output Rules: 1. Your response must be **only a valid JSON object**, with no explanations or extra text. 2. The output must start with `{{` and end with `}}`. 3. Absolutely do not add any introductory, concluding, or summary sentences like "Analysis result...", "These symbols are..." before or after the JSON."""

            if output_file_path.exists():
                print(f"⏭️ 건너뛰기: 이미 파일이 존재합니다: {output_file_path}")
            else:
                prompt_for_api = {
                    "messages": [
                        {
                            "role": "user",
                            "parts": [full_prompt]
                        }
                    ]
                }

                print(f"🔹 Gemini로 요청 전송 중...")
                api_reply = GeminiHandler.ask(prompt_for_api)

                output_dir.mkdir(parents=True, exist_ok=True)

                GeminiHandler.save_content(api_reply, output_filename, local_dir=str(output_dir))
                print(f"✅ 처리 성공: {output_filename}")

            print(f"--- 파일 처리 완료, 10초 대기 ---")
            time.sleep(1)

        except json.JSONDecodeError:
            print(f"🚨 파일이 올바른 JSON 형식이 아닙니다. 건너뜁니다: {filename_base}")
            continue
        except Exception as e:
            print(f"🚨 파일 처리 중 심각한 오류 발생 ({filename_base}): {e}")
            continue

    print("\n🎉 모든 파일 처리가 완료되었습니다.")


if __name__ == "__main__":
    main()
