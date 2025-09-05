import json
import shutil
import multiprocessing
from pathlib import Path
from tqdm import tqdm
from typing import Dict


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

SOURCE_INPUT_ROOT = PROJECT_ROOT / 'llm_training_inputs'
SPLIT_DATA_ROOT = PROJECT_ROOT / 'llm_training_data_split'
SPLIT_INPUT_ROOT = SPLIT_DATA_ROOT / 'inputs'

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
    'extensions': ['extensions', 'classes', 'structs', 'enums', 'protocols'],
    'typealiases': ['typealiases', 'classes', 'structs', 'enums', 'protocols', 'extensions']
}


def setup_directories():
    """결과를 저장할 디렉토리를 준비합니다."""
    print("결과 디렉토리를 초기화합니다...")
    if SPLIT_DATA_ROOT.exists():
        shutil.rmtree(SPLIT_DATA_ROOT)
    SPLIT_INPUT_ROOT.mkdir(parents=True, exist_ok=True)
    print("디렉토리 준비 완료.")


def split_single_input_file(file_path: Path):
    """
    하나의 원본 input 파일을 CONTEXT_MAP 규칙에 따라 여러 개의 작은 input 파일로 분할하고,
    생성된 파일 수를 반환합니다.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        created_files_count = 0
        instruction = data.get("instruction")
        original_input = data.get("input", {})
        original_symbols = original_input.get("symbol_data_for_analysis", {})

        base_name = file_path.stem.replace('training_input_', '')
        relative_parent = file_path.relative_to(SOURCE_INPUT_ROOT).parent

        for group_name, source_categories in CONTEXT_MAP.items():
            # 1. 분할된 Input 데이터 생성
            grouped_input_symbols = {}
            for category in source_categories:
                if category in original_symbols:
                    grouped_input_symbols[category] = original_symbols[category]

            # 그룹에 해당하는 심볼이 없으면 이 그룹은 건너뜀
            if not grouped_input_symbols:
                continue

            # 2. 새로운 Input 객체 구성
            new_input_obj = original_input.copy()
            new_input_obj['symbol_data_for_analysis'] = grouped_input_symbols

            final_input_record = {
                "instruction": instruction,
                "input": new_input_obj,
                "output": ""  # Output 필드는 비워둠
            }

            # 3. 분할된 파일 저장
            group_dir_name = f"{group_name}_group"
            input_save_dir = SPLIT_INPUT_ROOT / relative_parent / group_dir_name
            input_save_dir.mkdir(parents=True, exist_ok=True)
            input_filename = f"input_{base_name}_{group_dir_name}.json"

            with open(input_save_dir / input_filename, 'w', encoding='utf-8') as f:
                json.dump(final_input_record, f, indent=2, ensure_ascii=False)

            created_files_count += 1

        return created_files_count
    except Exception as e:
        return f"오류: {file_path.name} 처리 중 - {e}"


def main():
    """메인 실행 함수"""
    setup_directories()

    source_files = sorted(list(SOURCE_INPUT_ROOT.rglob("*.json")))
    if not source_files:
        print("분할할 원본 입력 파일이 없습니다.")
        return

    print(f"\n🚀 총 {len(source_files)}개의 원본 입력 파일을 분할합니다...")

    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = list(
            tqdm(pool.imap_unordered(split_single_input_file, source_files), total=len(source_files),
                 desc="Input 파일 분할 중"))

    errors = []
    total_split_files_created = 0
    for res in results:
        if isinstance(res, int):
            total_split_files_created += res
        elif isinstance(res, str):
            errors.append(res)

    print("\n🎉 분할 작업 완료!")
    if errors:
        print(f"   - {len(errors)}개의 파일 처리 중 오류가 발생했습니다.")
        for err in errors[:5]:
            print(f"     - {err}")

    print(f"   - 총 {total_split_files_created}개의 분할된 input 파일이 생성되었습니다.")
    print(f"   - 결과는 '{SPLIT_INPUT_ROOT}' 폴더에서 확인하실 수 있습니다.")


if __name__ == '__main__':
    main()

