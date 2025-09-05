import json
import shutil
import re
from pathlib import Path
from collections import defaultdict
import multiprocessing
from tqdm import tqdm
from typing import Dict, Any

# --- 경로 상수 ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

VALIDATED_DATA_ROOT = PROJECT_ROOT / 'llm_training_data_validated'
SPLIT_DATA_ROOT = PROJECT_ROOT / 'llm_training_data_split'
SPLIT_INPUT_DIR = SPLIT_DATA_ROOT / 'inputs'
SPLIT_OUTPUT_DIR = SPLIT_DATA_ROOT / 'outputs'

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
    if SPLIT_DATA_ROOT.exists(): shutil.rmtree(SPLIT_DATA_ROOT)
    SPLIT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    SPLIT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("디렉토리 준비 완료.")


def normalize_symbol_name(name: str) -> str:
    """심볼 이름에서 파라미터 부분을 제거하여 정규화합니다. (e.g., 'myFunc(a: Int)' -> 'myFunc')"""
    return name.split('(')[0]


def parse_thinking_block(thinking_text: str) -> Dict[str, str]:
    """<thinking> 블록의 텍스트를 파싱하여, 정규화된 심볼 이름을 키로 하는 딕셔너리로 만듭니다."""
    # 정규식 패턴: "**Category `SymbolName`**:"으로 시작하는 블록을 찾음
    pattern = re.compile(r"(\*\*.+?`(.+?)`\*\*:.+?)(?=\n\n\*\*|\Z)", re.DOTALL)
    matches = pattern.finditer(thinking_text)
    reasoning_map = {}
    for match in matches:
        full_block = match.group(1).strip()
        symbol_name = match.group(2).strip()
        normalized_name = normalize_symbol_name(symbol_name)
        reasoning_map[normalized_name] = full_block
    return reasoning_map


def split_single_file(file_path: Path):
    """하나의 검증된 파일을 CONTEXT_MAP 규칙에 따라 여러 개의 작은 파일로 분할하고, 생성된 파일 수를 반환합니다."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # [수정] 생성된 파일 수를 세기 위한 카운터
        created_files_count = 0

        instruction = data.get("instruction")
        original_input = data.get("input", {})
        full_output = data.get("output", {})

        original_symbols = original_input.get("symbol_data_for_analysis", {})
        json_output = full_output.get("json_output", {})

        base_name = file_path.stem.replace('validated_', '')
        relative_parent = file_path.relative_to(VALIDATED_DATA_ROOT).parent

        full_thinking_content = full_output.get("thinking", "")
        reasoning_map = parse_thinking_block(full_thinking_content)

        for group_name, source_categories in CONTEXT_MAP.items():
            grouped_input_symbols = {}
            for category in source_categories:
                if category in original_symbols:
                    grouped_input_symbols[category] = original_symbols[category]

            if not grouped_input_symbols:
                continue

            new_input_obj = original_input.copy()
            new_input_obj['symbol_data_for_analysis'] = grouped_input_symbols

            current_group_symbol_names = {
                normalize_symbol_name(symbol['symbol_name'])
                for category in grouped_input_symbols.values()
                for symbol in category
            }

            filtered_thinking_parts = [
                block for name, block in reasoning_map.items() if name in current_group_symbol_names
            ]
            filtered_thinking = "\n\n".join(filtered_thinking_parts)

            grouped_output_symbols = {}
            if group_name in json_output and json_output.get(group_name):
                grouped_output_symbols = {group_name: json_output[group_name]}

            is_positive_sample = bool(grouped_output_symbols)
            is_high_confidence_negative = (not is_positive_sample) and any(
                cat in original_symbols for cat in source_categories)

            if not (is_positive_sample or is_high_confidence_negative):
                continue

            group_dir_name = f"{group_name}_group"

            input_save_dir = SPLIT_INPUT_DIR / relative_parent / group_dir_name
            input_save_dir.mkdir(parents=True, exist_ok=True)
            input_filename = f"input_{base_name}_{group_dir_name}.json"

            final_input_record = {
                "instruction": instruction,
                "input": new_input_obj,
                "output": ""
            }
            with open(input_save_dir / input_filename, 'w', encoding='utf-8') as f:
                json.dump(final_input_record, f, indent=2, ensure_ascii=False)

            # [수정] input 파일 생성 시 카운트 증가
            created_files_count += 1

            if is_positive_sample:
                output_save_dir = SPLIT_OUTPUT_DIR / relative_parent / group_dir_name
                output_save_dir.mkdir(parents=True, exist_ok=True)
                output_filename = f"output_{base_name}_{group_dir_name}.json"

                final_output_record = {
                    "thinking": filtered_thinking,
                    "json_output": grouped_output_symbols
                }
                with open(output_save_dir / output_filename, 'w', encoding='utf-8') as f:
                    json.dump(final_output_record, f, indent=2, ensure_ascii=False)

                # [수정] output 파일 생성 시 카운트 증가
                created_files_count += 1

        # [수정] 성공 시 생성된 파일 수를 반환
        return created_files_count
    except Exception as e:
        return f"오류: {file_path.name} 처리 중 - {e}"


def main():
    """메인 실행 함수"""
    setup_directories()

    validated_files = sorted(list(VALIDATED_DATA_ROOT.rglob("*.json")))
    if not validated_files:
        print("분할할 검증된 파일이 없습니다.")
        return

    print(f"\n🚀 2단계: 총 {len(validated_files)}개의 검증된 파일을 분할합니다...")

    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = list(
            tqdm(pool.imap_unordered(split_single_file, validated_files), total=len(validated_files), desc="파일 분할 중"))

    # [수정] 결과를 분석하여 총 생성 파일 수와 오류를 집계합니다.
    errors = []
    total_split_files_created = 0
    for res in results:
        if isinstance(res, int):
            total_split_files_created += res
        elif isinstance(res, str):
            errors.append(res)

    print("\n🎉 2단계 완료!")
    if errors:
        print(f"   - {len(errors)}개의 파일 처리 중 오류가 발생했습니다.")
        for err in errors[:5]:
            print(f"     - {err}")

    print(f"   - 모든 파일이 성공적으로 분할되었습니다.")
    # [수정] 최종 생성된 파일 수를 출력합니다.
    print(f"   - 총 {total_split_files_created}개의 분할된 파일(inputs/outputs)이 생성되었습니다.")


if __name__ == '__main__':
    main()

