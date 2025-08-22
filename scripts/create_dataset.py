import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BASE_DIR = PROJECT_ROOT / "jsonl"
INPUT_DIR = BASE_DIR / "input_label_split"
OUTPUT_DIR = BASE_DIR / "output_label_split"
FINAL_DATASET_FILE = PROJECT_ROOT / "alpaca_dataset.jsonl"
NO_EXCLUSION_MESSAGE = "There are no identifiers that need to be excluded from obfuscation."


def map_output_files(output_dir: str) -> Dict[str, str]:
    """
    output 디렉토리를 미리 스캔하여, 'output_' 뒷부분을 key로,
    파일의 전체 경로를 value로 하는 딕셔너리(지도)를 생성합니다.
    """
    file_map = {}
    if not os.path.isdir(output_dir):
        return file_map

    for root, _, files in os.walk(output_dir):
        for filename in files:
            if filename.startswith("output_") and filename.endswith(".jsonl"):
                key = filename[len("output"):]
                file_map[key] = os.path.join(root, filename)
    print(f"Found and mapped {len(file_map)} output files.")
    return file_map


def create_alpaca_dataset():
    """
    'input_...'과 'output_...' 이름 규칙에 따라 파일을 매칭하고,
    각 input 심벌에 mapping 정보를 포함하여 데이터셋을 생성합니다.
    """
    if not os.path.isdir(INPUT_DIR):
        print(f"Error: Input directory not found at '{INPUT_DIR}'")
        return

    all_records: List[Dict[str, str]] = []
    main_instruction = None

    print("Mapping all output files first...")
    output_file_map = map_output_files(OUTPUT_DIR)

    print("Starting dataset creation...")

    for root, _, files in os.walk(INPUT_DIR):
        for filename in files:
            if not (filename.startswith("input_") and filename.endswith(".jsonl")):
                continue

            input_file_path = Path(root) / filename

            file_mapping = None
            symbol_lines_data = []

            # 1. 파일을 한번 스캔하여 meta(instruction, mapping) 정보와 심벌 데이터를 분리
            try:
                with open(input_file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            if 'meta' in data:
                                if main_instruction is None and 'prompt_context' in data['meta']:
                                    main_instruction = data['meta']['prompt_context']
                                    print("Successfully extracted main instruction.")
                                if 'mapping' in data['meta']:
                                    file_mapping = data['meta']['mapping']
                            else:
                                symbol_lines_data.append(data)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Warning: Could not read {input_file_path}. Error: {e}")
                continue

            # instruction이나 mapping 정보가 없으면 해당 파일을 건너뜀
            if not main_instruction:
                print(f"Warning: Could not find instruction in {filename} or any previous file. Skipping.")
                continue
            if not file_mapping:
                print(f"Warning: Could not find mapping in {filename}. Skipping.")
                continue

            # 2. 심벌 데이터와 output 파일을 매칭하여 최종 레코드 생성
            file_suffix = filename[len("input"):]

            # CASE 2: 매칭되는 출력 파일이 있는 경우
            if file_suffix in output_file_map:
                output_file_path = output_file_map[file_suffix]
                print(f"Processing matched pair: {filename} -> {os.path.basename(output_file_path)}")
                try:
                    with open(output_file_path, 'r', encoding='utf-8') as f_out:
                        output_lines_data = [json.loads(line) for line in f_out if line.strip()]

                    if len(symbol_lines_data) != len(output_lines_data):
                        print(f"Warning: Mismatch in line count for {filename}. Skipping.")
                        continue

                    for i, symbol_data in enumerate(symbol_lines_data):
                        new_input_obj = {"mapping": file_mapping, "symbol_data": symbol_data}

                        formatted_output = json.dumps(output_lines_data[i], separators=(',', ':'))

                        alpaca_record = {
                            "instruction": main_instruction,
                            "input": json.dumps(new_input_obj, ensure_ascii=False),
                            "output": formatted_output
                        }
                        all_records.append(alpaca_record)

                except Exception as e:
                    print(f"Error processing file pair for {filename}. Error: {e}")

            # CASE 1: 매칭되는 출력 파일이 없는 경우
            else:
                print(f"Info: Output file not found for '{filename}'. Using default message.")
                for symbol_data in symbol_lines_data:
                    new_input_obj = {"mapping": file_mapping, "symbol_data": symbol_data}

                    alpaca_record = {
                        "instruction": main_instruction,
                        "input": json.dumps(new_input_obj, ensure_ascii=False),
                        "output": NO_EXCLUSION_MESSAGE
                    }
                    all_records.append(alpaca_record)

    # 모든 레코드를 최종 파일에 저장
    try:
        with open(FINAL_DATASET_FILE, 'w', encoding='utf-8') as f_final:
            for record in all_records:
                f_final.write(json.dumps(record, ensure_ascii=False) + '\n')

        print(f"\n✅ Done!")
        print(f"Successfully created '{FINAL_DATASET_FILE}' with {len(all_records)} records.")

    except IOError as e:
        print(f"Error writing to final dataset file '{FINAL_DATASET_FILE}'. Error: {e}")


if __name__ == "__main__":
    create_alpaca_dataset()