import os
import json
import time

# 사용하지 않는 핸들러는 주석 처리하거나 삭제할 수 있습니다.
# from gpt_handler import GPTHandler
# from claude_handler import ClaudeHandler
from gemini_handler import GeminiHandler

INPUT_ROOT = 'input_label'
OUTPUT_ROOT = 'output_label'
TARGET_FOLDERS = ['gemini_generated']


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
    START_INDEX = 1
    END_INDEX = 575

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

        try:
            original_filename_no_ext = os.path.splitext(filename_base)[0]

            if original_filename_no_ext.startswith('input_pattern_'):
                pattern_part = original_filename_no_ext.replace('input_pattern_', '')
                output_filename = f"output_pattern_{pattern_part}.json"
            else:
                output_filename = f"output_pattern_{original_filename_no_ext}.json"

            # 최종 출력 파일 경로를 미리 확인
            output_path_check = os.path.join(OUTPUT_ROOT, 'gemini_generated', output_filename)
            if os.path.exists(output_path_check):
                print(f"--- [{i}/{total_files}] 건너뛰기: 이미 파일이 존재합니다 ({output_filename}) ---")
                continue

            print(f"\n--- [{i}/{total_files}] 파일 처리 중: {filename_base} ---")

            with open(file_path, 'r', encoding='utf-8') as f:
                request_payload = json.load(f)

            prompt_instructions = request_payload.get("meta", {}).get("prompt_context", "")
            symbol_data_to_process = request_payload.get("decisions", {})

            if not prompt_instructions or not symbol_data_to_process:
                print(f"🚨 오류: {filename_base} 파일에 'meta.prompt_context' 또는 'decisions' 데이터가 없습니다. 건너뜁니다.")
                continue

            drive_folder_suffix = os.path.splitext(output_filename)[0]

            full_prompt = f"""{prompt_instructions}

# JSON data to analyze:
```json
{json.dumps(symbol_data_to_process, indent=2, ensure_ascii=False)}
```

[CRITICAL] Final Output Rules: 1. Your response must be **only a valid JSON object**, with no explanations or extra text. 2. The output must start with `{{` and end with `}}`. 3. Absolutely do not add any introductory, concluding, or summary sentences like "Analysis result...", "These symbols are..." before or after the JSON."""

            # --- Gemini 처리 ---
            try:
                print(f"🔹 Gemini로 요청 전송 중...")
                gemini_reply = GeminiHandler.ask(full_prompt)

                output_path_gemini = os.path.join(OUTPUT_ROOT, 'gemini_generated')
                drive_folder_gemini = f"training_set/gemini_generated/output/json/{drive_folder_suffix}"

                GeminiHandler.save_and_upload(gemini_reply, output_filename, drive_folder_gemini,
                                              local_dir=output_path_gemini)
                print(f"✅ Gemini 처리 성공: {output_filename}")

            except Exception as e:
                print(f"❌ Gemini 처리 오류 ({output_filename}): {e}")

            print(f"--- 파일 처리 완료, 10초 대기 ---")
            time.sleep(10)

        except json.JSONDecodeError:
            print(f"🚨 파일이 올바른 JSON 형식이 아닙니다. 건너뜁니다: {filename_base}")
            continue
        except Exception as e:
            print(f"🚨 파일 처리 중 심각한 오류 발생 ({filename_base}): {e}")
            continue

    print("\n🎉 모든 파일 처리가 완료되었습니다.")


if __name__ == "__main__":
    main()
