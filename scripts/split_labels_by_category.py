import os
import json
import shutil
from multiprocessing import Pool, cpu_count
from pathlib import Path
import re
from collections import defaultdict

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INPUT_ROOT_DIR = PROJECT_ROOT / 'input_label'
OUTPUT_ROOT_DIR = PROJECT_ROOT / 'output_label'
MODEL_SUB_DIRS = ['claude_generated', 'gemini_generated']

SPLIT_INPUT_DIR = PROJECT_ROOT / 'input_label_split'
SPLIT_OUTPUT_DIR = PROJECT_ROOT / 'output_label_split'

CONTEXT_MAP = {
    'methods': ['methods', 'initializers', 'deinitializers', 'subscripts', 'variables'],
    'properties': ['properties'],
    'variables': ['variables'],
    'initializers': ['classes', 'structs', 'enums', 'protocols', 'extensions', 'initializers'],
    'deinitializers': ['classes', 'structs', 'enums', 'protocols', 'extensions', 'deinitializers'],
    'subscripts': ['classes', 'structs', 'enums', 'protocols', 'extensions', 'subscripts'],
    'enumCases': ['enums', 'enumCases'],
    'classes': ['classes', 'protocols', 'structs'],
    'structs': ['structs', 'protocols', 'classes'],
    'enums': ['enums', 'protocols', 'enumCases', 'classes'],
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
    하나의 (input.json, output.json) 쌍을 그룹화하여 분할합니다.
    Positive 샘플(Input/Output 쌍)과 Negative 샘플(Input 단독)을 모두 생성합니다.
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
        original_input_decisions = input_data.get('decisions', {})
        base_name = re.sub(r'^(input_|output_)', '', input_file_path.stem)

        for group_name, source_categories in CONTEXT_MAP.items():

            # Positive / Negative 샘플 여부 판단
            is_positive = group_name in output_data and output_data[group_name]
            is_high_confidence_negative = (not is_positive) and (group_name in original_input_decisions)

            # Positive 샘플이거나 고신뢰도 Negative 샘플일 경우에만 Input 파일 생성
            if is_positive or is_high_confidence_negative:

                # 그룹화된 Input 데이터 구성
                new_input_decisions = {}
                for category in source_categories:
                    if category in original_input_decisions:
                        new_input_decisions[category] = original_input_decisions[category]

                if not new_input_decisions:
                    continue

                group_dir_name = f"{group_name}_group"
                final_input_structure = {"mapping": mapping_data,
                                         "data": {"meta": meta_data, "decisions": new_input_decisions}}

                # Input 파일 저장
                input_save_dir = SPLIT_INPUT_DIR / model_dir / group_dir_name
                input_save_dir.mkdir(parents=True, exist_ok=True)
                input_filename = f"input_{base_name}_{group_dir_name}.json"
                with open(input_save_dir / input_filename, 'w', encoding='utf-8') as f:
                    json.dump(final_input_structure, f, ensure_ascii=False, indent=2)

                # Positive 샘플인 경우에만 Output 파일도 함께 저장
                if is_positive:
                    final_output_structure = {group_name: output_data[group_name]}
                    output_save_dir = SPLIT_OUTPUT_DIR / model_dir / group_dir_name
                    output_save_dir.mkdir(parents=True, exist_ok=True)
                    output_filename = f"output_{base_name}_{group_dir_name}.json"
                    with open(output_save_dir / output_filename, 'w', encoding='utf-8') as f:
                        json.dump(final_output_structure, f, ensure_ascii=False, indent=2)

        return {"model": model_dir, "status": "SUCCESS", "message": f"'{input_file_path.name}' 처리"}

    except Exception as e:
        return {"model": model_dir, "status": "ERROR", "message": f"'{input_file_path.name}' 처리 중 오류: {e}"}


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

    print("\n\n" + "=" * 50)
    print("📊 최종 처리 결과 요약")
    print("=" * 50)

    file_summary = defaultdict(lambda: defaultdict(int))
    error_details = []

    for res in results:
        model = res["model"]
        status = res["status"]
        file_summary[model][status] += 1
        if status == "ERROR":
            error_details.append(f"[{model}] {res['message']}")

    grand_total_files = 0
    for model in sorted(file_summary.keys()):
        stats = file_summary[model]
        total_files = sum(stats.values())
        grand_total_files += total_files

        print(f"\n--- 모델: {model} (총 {total_files}개 파일) ---")
        print(f"  - ✅ 파일 처리 성공: {stats.get('SUCCESS', 0)}개")
        print(f"  - 🔥 파일 처리 오류: {stats.get('ERROR', 0)}개")

    print("\n" + "=" * 50)
    print(f"📈 전체 처리 파일 수: {grand_total_files}개")
    print("=" * 50)

    if error_details:
        print("\n\n" + "🔥 오류 상세 내역:")
        print("-" * 40)
        for detail in sorted(error_details):
            print(detail)

    print("\n모든 파일 분할 작업이 완료되었습니다.")


if __name__ == '__main__':
    main()