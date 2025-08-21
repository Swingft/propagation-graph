import os
import json
import time
import sys

from claude_handler import ClaudeHandler
from gemini_handler import GeminiHandler


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

INPUT_ROOT = os.path.join(PROJECT_ROOT, 'input_label')
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, 'output_label')

sys.path.append(SCRIPT_DIR)
TARGET_FOLDERS = ['claude_generated', 'gemini_generated']


def find_json_files():
    """
    지정된 입력 디렉토리에서 모든 .json 파일을 찾음
    'jsonl_format' 하위 디렉토리는 제외함
    """
    files_to_process = []
    for folder in TARGET_FOLDERS:
        input_dir = os.path.join(INPUT_ROOT, folder)
        if not os.path.isdir(input_dir):
            print(f"경고: 입력 디렉토리를 찾을 수 없습니다, 건너뜁니다: {input_dir}")
            continue

        for root, dirs, files in os.walk(input_dir):
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

    START_INDEX = 575
    END_INDEX = None

    json_files = find_json_files()
    if not json_files:
        print("처리할 .json 파일을 찾지 못했습니다. 종료합니다.")
        return

    total_files = len(json_files)
    print(f"총 {total_files}개의 .json 파일을 처리합니다.")
    print(f"실행 범위: {START_INDEX}번 파일부터 {END_INDEX or '끝'}번 파일까지")

    for i, file_path in enumerate(json_files, start=1):
        if i < START_INDEX:
            continue
        if END_INDEX is not None and i > END_INDEX:
            print(f"\n--- 종료 인덱스({END_INDEX})에 도달하여 처리를 중단합니다. ---")
            break

        filename_base = os.path.basename(file_path)
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

            original_filename_no_ext = os.path.splitext(filename_base)[0]

            if original_filename_no_ext.startswith('input_pattern_'):
                pattern_part = original_filename_no_ext.replace('input_pattern_', '')
                output_filename = f"output_pattern_{pattern_part}.json"
                drive_folder_suffix = f"output_pattern_{pattern_part}"
            else:
                output_filename = f"output_pattern_{original_filename_no_ext}.json"
                drive_folder_suffix = f"output_pattern_{original_filename_no_ext}"

            full_prompt = f"""{prompt_instructions}

# JSON data to analyze:
```json
{json.dumps(symbol_data_to_process, indent=2, ensure_ascii=False)}
```

[CRITICAL] Final Output Rules: 1. Your response must be **only a valid JSON object**, with no explanations or extra text. 2. The output must start with `{{` and end with `}}`. 3. Absolutely do not add any introductory, concluding, or summary sentences like "Analysis result...", "These symbols are..." before or after the JSON."""

            is_claude_file = 'claude_generated' in file_path
            is_gemini_file = 'gemini_generated' in file_path

            # --- Claude 처리 로직 ---
            if is_claude_file:
                try:
                    output_path_claude = os.path.join(OUTPUT_ROOT, 'claude_generated')
                    if os.path.exists(os.path.join(output_path_claude, output_filename)):
                        print(f"⏭️ Claude 건너뛰기: 이미 파일이 존재합니다.")
                    else:
                        print(f"🔹 Claude로 요청 전송 중...")
                        claude_reply = ClaudeHandler.ask(full_prompt)
                        drive_folder_claude = f"training_set/claude_generated/output/json/{drive_folder_suffix}"
                        ClaudeHandler.save_and_upload(claude_reply, output_filename, drive_folder_claude, local_dir=output_path_claude)
                        print(f"✅ Claude 처리 성공: {output_filename}")
                except Exception as e:
                    print(f"❌ Claude 처리 오류 ({output_filename}): {e}")

            # --- Gemini 처리 로직 ---
            # if is_gemini_file:
            #     try:
            #         output_path_gemini = os.path.join(OUTPUT_ROOT, 'gemini_generated')
            #         if os.path.exists(os.path.join(output_path_gemini, output_filename)):
            #             print(f"⏭️ Gemini 건너뛰기: 이미 파일이 존재합니다.")
            #         else:
            #             print(f"🔹 Gemini로 요청 전송 중...")
            #             gemini_reply = GeminiHandler.ask(full_prompt)
            #             drive_folder_gemini = f"training_set/gemini_generated/output/json/{drive_folder_suffix}"
            #             GeminiHandler.save_and_upload(gemini_reply, output_filename, drive_folder_gemini, local_dir=output_path_gemini)
            #             print(f"✅ Gemini 처리 성공: {output_filename}")
            #     except Exception as e:
            #         print(f"❌ Gemini 처리 오류 ({output_filename}): {e}")

            print(f"--- 파일 처리 완료, 12초 대기 ---")
            time.sleep(12)

        except json.JSONDecodeError:
            print(f"🚨 파일이 올바른 JSON 형식이 아닙니다. 건너뜁니다: {filename_base}")
            continue
        except Exception as e:
            print(f"🚨 파일 처리 중 심각한 오류 발생 ({filename_base}): {e}")
            continue

    print("\n🎉 모든 파일 처리가 완료되었습니다.")


if __name__ == "__main__":
    main()
