import os
import json
import shutil
from multiprocessing import Pool, cpu_count
from pathlib import Path
import re


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INPUT_ROOT_DIR = PROJECT_ROOT / 'input_label'
OUTPUT_ROOT_DIR = PROJECT_ROOT / 'output_label'
MODEL_SUB_DIRS = ['claude_generated', 'gemini_generated', 'gpt_generated']  # gpt_generated도 추가

SPLIT_INPUT_DIR = PROJECT_ROOT / 'input_label_split'
SPLIT_OUTPUT_DIR = PROJECT_ROOT / 'output_label_split'

# --- 각 Output 카테고리를 예측하기 위해 필요한 Input 그룹들의 규칙 정의 ---
CONTEXT_MAP = {
    'methods': ['classes', 'structs', 'enums', 'protocols', 'extensions'],
    'properties': ['classes', 'structs', 'enums', 'protocols', 'extensions'],
    'variables': ['classes', 'structs', 'enums', 'protocols', 'extensions'],
    'initializers': ['classes', 'structs', 'enums', 'protocols', 'extensions'],
    'deinitializers': ['classes', 'structs', 'enums', 'protocols', 'extensions'],
    'subscripts': ['classes', 'structs', 'enums', 'protocols', 'extensions'],
    'enumCases': ['enums'],
    'classes': ['classes', 'protocols'],
    'structs': ['structs', 'protocols'],
    'enums': ['enums', 'protocols'],
    'protocols': ['protocols'],
    'extensions': ['extensions', 'classes', 'structs', 'enums', 'protocols']
}


def setup_directories():
    """결과를 저장할 디렉토리를 준비합니다."""
    print("결과 디렉토리를 초기화합니다...")
    if SPLIT_INPUT_DIR.exists(): shutil.rmtree(SPLIT_INPUT_DIR)
    if SPLIT_OUTPUT_DIR.exists(): shutil.rmtree(SPLIT_OUTPUT_DIR)
    SPLIT_INPUT_DIR.mkdir(exist_ok=True)
    SPLIT_OUTPUT_DIR.mkdir(exist_ok=True)
    print("디렉토리 준비 완료.")


def process_file_pair(task_info):
    """
    하나의 (input.json, output.json) 쌍을 카테고리 단위로 분할합니다.
    Positive/Negative 샘플을 모두 생성합니다.
    """
    input_file_path, output_file_path, model_dir = task_info
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            full_input_data = json.load(f)

        output_data = {}
        if output_file_path.exists():
            with open(output_file_path, 'r', encoding='utf-8') as f:
                output_data = json.load(f)

        mapping_data = full_input_data.get('mapping', {})
        input_data = full_input_data.get('data', {})
        meta_data = input_data.get('meta', {})
        input_decisions = input_data.get('decisions', {})

        for category in input_decisions.keys():
            if category not in CONTEXT_MAP:
                continue

            required_context_keys = CONTEXT_MAP.get(category, [])
            new_decisions = {}
            for key in required_context_keys:
                if key in input_decisions:
                    new_decisions[key] = input_decisions[key]

            if not new_decisions:
                continue

            final_input_structure = {
                "mapping": mapping_data,
                "data": {"meta": meta_data, "decisions": new_decisions}
            }

            base_name = re.sub(r'^(input_|output_)', '', input_file_path.stem)

            # Positive 샘플 (Output이 존재하는 경우)
            if category in output_data and output_data[category]:
                split_output_data = {category: output_data[category]}
                output_save_dir = SPLIT_OUTPUT_DIR / model_dir / category
                output_save_dir.mkdir(parents=True, exist_ok=True)
                output_filename = f"output_{base_name}_{category}.json"
                with open(output_save_dir / output_filename, 'w', encoding='utf-8') as f:
                    json.dump(split_output_data, f, ensure_ascii=False, indent=2)

                input_save_dir = SPLIT_INPUT_DIR / model_dir / category
                input_save_dir.mkdir(parents=True, exist_ok=True)
                input_filename = f"input_{base_name}_{category}.json"
                with open(input_save_dir / input_filename, 'w', encoding='utf-8') as f:
                    json.dump(final_input_structure, f, ensure_ascii=False, indent=2)

            # Negative 샘플 (Output이 존재하지 않는 경우)
            else:
                input_save_dir = SPLIT_INPUT_DIR / model_dir / category
                input_save_dir.mkdir(parents=True, exist_ok=True)
                input_filename = f"input_{base_name}_{category}.json"
                with open(input_save_dir / input_filename, 'w', encoding='utf-8') as f:
                    json.dump(final_input_structure, f, ensure_ascii=False, indent=2)

        return f"✅ '{input_file_path.name}' 처리 완료"
    except Exception as e:
        return f"🔥 '{input_file_path.name}' 처리 중 오류 발생: {e}"


def main():
    """메인 실행 함수"""
    setup_directories()
    tasks = []
    print("처리할 Input/Output 파일 쌍을 검색 및 매칭합니다...")

    input_files_map, output_files_map = {}, {}

    for sub_dir in MODEL_SUB_DIRS:
        input_dir = INPUT_ROOT_DIR / sub_dir
        if input_dir.is_dir():
            count = 0
            for filename in os.listdir(input_dir):
                match = re.search(r'input_(.+)\.json', filename)
                if match:
                    key = match.group(1)
                    input_files_map[(key, sub_dir)] = input_dir / filename
                    count += 1
            print(f"   - '{sub_dir}'에서 Input 파일 {count}개 발견")

        output_dir = OUTPUT_ROOT_DIR / sub_dir
        if output_dir.is_dir():
            for filename in os.listdir(output_dir):
                match = re.search(r'output_(.+)\.json', filename)
                if match:
                    key = match.group(1)
                    output_files_map[(key, sub_dir)] = output_dir / filename

    for (key, model_dir), input_path in input_files_map.items():
        output_path = output_files_map.get((key, model_dir), Path())
        tasks.append((input_path, output_path, model_dir))

    if not tasks:
        print("처리할 파일 쌍을 찾지 못했습니다. 파일 이름 규칙(input_*.json, output_*.json)을 확인해주세요.")
        return

    print(f"\n총 {len(tasks)}개의 파일 세트에 대해 분할 작업을 시작합니다...")
    with Pool(processes=cpu_count()) as pool:
        results = pool.map(process_file_pair, tasks)
        for res in results: print(res)
    print("\n모든 파일 분할 작업이 완료되었습니다.")


if __name__ == '__main__':
    main()
