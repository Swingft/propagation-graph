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


def map_output_files(output_dir: Path) -> Dict[str, Path]:
    """
    output 디렉토리를 스캔하여 'output_' 접두사를 제외한 나머지 부분을 key로,
    파일의 전체 경로를 value로 하는 딕셔너리를 생성합니다.
    """
    file_map = {}
    if not output_dir.is_dir():
        return file_map

    for file_path in output_dir.rglob("output_*.jsonl"):
        key = file_path.name.replace("output_", "", 1)
        file_map[key] = file_path

    print(f"Found and mapped {len(file_map)} output files.")
    return file_map


def create_alpaca_dataset():
    """
    'input_*.jsonl' 파일 하나를 통째로 'input'으로, 'output_*.jsonl' 파일 하나를
    통째로 'output'으로 하는 Alpaca 데이터셋 레코드를 생성합니다.
    """
    if not INPUT_DIR.is_dir():
        print(f"Error: Input directory not found at '{INPUT_DIR}'")
        return

    all_records: List[Dict[str, str]] = []
    main_instruction = None
    no_exclusion_count = 0  # Negative 샘플 카운터
    files_processed = 0

    print("Mapping all output files first...")
    output_file_map = map_output_files(OUTPUT_DIR)

    print("Starting dataset creation...")

    for input_file_path in INPUT_DIR.rglob("input_*.jsonl"):
        files_processed += 1
        file_mapping = None
        symbol_lines_data = []

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

        if not main_instruction or not file_mapping:
            print(f"Warning: Critical meta information missing in {input_file_path.name}. Skipping.")
            continue

        new_input_obj = {
            "mapping": file_mapping,
            "symbols": symbol_lines_data  # 'symbol_data' -> 'symbols' (복수형), 리스트 전체를 할당
        }
        input_string = json.dumps(new_input_obj, ensure_ascii=False)

        output_string = ""
        file_suffix = input_file_path.name.replace("input_", "", 1)

        # Positive Sample 처리
        if file_suffix in output_file_map:
            output_file_path = output_file_map[file_suffix]
            try:
                with open(output_file_path, 'r', encoding='utf-8') as f_out:
                    output_lines_data = [json.loads(line) for line in f_out if line.strip()]
                # 전체 리스트를 하나의 JSON 문자열로 만듦
                output_string = json.dumps(output_lines_data, ensure_ascii=False, separators=(',', ':'))
            except Exception as e:
                print(f"Error processing output file pair for {input_file_path.name}. Error: {e}")
                continue

        # Negative Sample 처리
        else:
            no_exclusion_count += 1
            output_string = NO_EXCLUSION_MESSAGE

        # --- 💡 3. 파일 하나당 하나의 레코드 생성 ---
        # symbol을 순회하는 루프가 없어지고, 파일당 한번만 레코드를 추가합니다.
        alpaca_record = {
            "instruction": main_instruction,
            "input": input_string,
            "output": output_string
        }
        all_records.append(alpaca_record)

    try:
        with open(FINAL_DATASET_FILE, 'w', encoding='utf-8') as f_final:
            for record in all_records:
                f_final.write(json.dumps(record, ensure_ascii=False) + '\n')

        matched_records = len(all_records) - no_exclusion_count
        print(f"\n✅ Done!")
        print(f"Processed {files_processed} input files to create {len(all_records)} records.")
        print("-" * 55)
        print(f"Successfully created '{FINAL_DATASET_FILE}'")
        print(f"  - 📝 Matched Records (Positive Samples): {matched_records}")
        print(f"  - 🤷‍♀️ Unmatched Records (Negative Samples): {no_exclusion_count}")
        print("-" * 55)

    except IOError as e:
        print(f"Error writing to final dataset file '{FINAL_DATASET_FILE}'. Error: {e}")


if __name__ == "__main__":
    create_alpaca_dataset()