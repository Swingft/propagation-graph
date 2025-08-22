import os
import json
from typing import Dict, Any, List, Optional

# --- 설정 ---
BASE_DIR = "jsonl"
INPUT_DIR = os.path.join(BASE_DIR, "input_label_split")
OUTPUT_DIR = os.path.join(BASE_DIR, "output_label_split")
FINAL_DATASET_FILE = "alpaca_dataset.jsonl"
NO_EXCLUSION_MESSAGE = "There are no identifiers that need to be excluded from obfuscation."


def find_main_instruction(input_dir: str) -> Optional[str]:
    """
    모든 입력 파일을 스캔하여 파인튜닝에 사용할 메인 instruction(지시문)을 찾습니다.
    'meta.prompt_context' 키에 있는 값을 사용합니다.
    """
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if not filename.endswith(".jsonl"):
                continue
            file_path = os.path.join(root, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            if "meta" in data and "prompt_context" in data["meta"]:
                                print("Successfully extracted main instruction.")
                                return data["meta"]["prompt_context"]
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Warning: Could not read {file_path}. Error: {e}")
    return None


def create_alpaca_dataset():
    """
    input/output 디렉토리를 탐색하며 JSONL 파일 라인을 쌍으로 묶어
    하나의 알파카 스타일 데이터셋 파일을 생성합니다.
    """
    if not os.path.isdir(INPUT_DIR):
        print(f"Error: Input directory not found at '{INPUT_DIR}'")
        return

    all_records: List[Dict[str, str]] = []
    # <<< 파일 단위 통계를 위한 변수 초기화
    processed_file_count = 0
    file_sizes: List[int] = []

    print("Searching for main instruction...")
    main_instruction = find_main_instruction(INPUT_DIR)
    if not main_instruction:
        print("Error: Could not find 'meta.prompt_context' in any input file. Aborting.")
        return

    print("Starting dataset creation...")

    # 전체 입력 디렉토리 구조 탐색
    for root, _, files in os.walk(INPUT_DIR):
        for filename in files:
            if not filename.endswith(".jsonl"):
                continue

            # <<< 파일 처리 개수 및 크기 계산
            processed_file_count += 1
            input_file_path = os.path.join(root, filename)
            file_sizes.append(os.path.getsize(input_file_path)) # 파일 크기를 바이트 단위로 리스트에 추가

            relative_path = os.path.relpath(input_file_path, INPUT_DIR)
            output_file_path = os.path.join(OUTPUT_DIR, relative_path)

            # Case 1: 대응하는 출력 파일이 없는 경우
            if not os.path.exists(output_file_path):
                print(f"Info: Output file not found for '{relative_path}'. Using default message for all entries.")
                try:
                    with open(input_file_path, 'r', encoding='utf-8') as f_in:
                        for line in f_in:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                input_data = json.loads(line)
                                if 'meta' in input_data:
                                    del input_data['meta']

                                alpaca_record = {
                                    "instruction": main_instruction,
                                    "input": json.dumps(input_data),
                                    "output": NO_EXCLUSION_MESSAGE
                                }
                                all_records.append(alpaca_record)

                            except json.JSONDecodeError:
                                print(f"Warning: Could not parse JSON in {relative_path}. Skipping line.")
                except Exception as e:
                    print(f"Error reading input file {input_file_path}. Error: {e}")
                continue

            # Case 2: 대응하는 출력 파일이 있는 경우
            print(f"Processing: {relative_path}")
            try:
                with open(input_file_path, 'r', encoding='utf-8') as f_in, \
                        open(output_file_path, 'r', encoding='utf-8') as f_out:

                    input_lines = f_in.readlines()
                    output_lines = f_out.readlines()

                    if len(input_lines) != len(output_lines):
                        print(f"Warning: Mismatch in line count for {relative_path}. Skipping.")
                        continue

                    for i in range(len(input_lines)):
                        input_line = input_lines[i].strip()
                        output_line = output_lines[i].strip()

                        if not input_line:
                            continue

                        try:
                            input_data = json.loads(input_line)
                            if 'meta' in input_data:
                                del input_data['meta']

                            formatted_output = ""
                            clean_output_str = output_line.split('//')[0].strip()
                            if clean_output_str:
                                output_data = json.loads(clean_output_str)
                                formatted_output = json.dumps(output_data, separators=(',', ':'))
                            else:
                                formatted_output = NO_EXCLUSION_MESSAGE

                            alpaca_record = {
                                "instruction": main_instruction,
                                "input": json.dumps(input_data),
                                "output": formatted_output
                            }
                            all_records.append(alpaca_record)

                        except json.JSONDecodeError as e:
                            print(f"Warning: Could not parse JSON on line {i + 1} of {relative_path}. Error: {e}. Skipping line.")
                        except Exception as e:
                            print(f"An unexpected error occurred processing line {i + 1} of {relative_path}. Error: {e}. Skipping line.")

            except Exception as e:
                print(f"Error opening or reading file pair for {relative_path}. Error: {e}")

    # 모든 레코드를 최종 파일에 저장
    try:
        with open(FINAL_DATASET_FILE, 'w', encoding='utf-8') as f_final:
            for record in all_records:
                f_final.write(json.dumps(record, ensure_ascii=False) + '\n')

        print("\n✅ Done!")
        print(f"Successfully created '{FINAL_DATASET_FILE}' with {len(all_records)} records.")

        # <<< 파일 단위 평균 용량 계산 및 출력
        print(f"Total .jsonl files processed: {processed_file_count}")
        if file_sizes:
            avg_size_bytes = sum(file_sizes) / len(file_sizes)
            # 크기에 따라 KB 또는 MB로 단위를 자동 변환하여 출력
            if avg_size_bytes > 1024 * 1024:
                avg_size_str = f"{avg_size_bytes / (1024 * 1024):.2f} MB"
            elif avg_size_bytes > 1024:
                avg_size_str = f"{avg_size_bytes / 1024:.2f} KB"
            else:
                avg_size_str = f"{avg_size_bytes:.2f} bytes"
            print(f"Average file size: {avg_size_str}")

    except IOError as e:
        print(f"Error writing to final dataset file '{FINAL_DATASET_FILE}'. Error: {e}")


if __name__ == "__main__":
    create_alpaca_dataset()