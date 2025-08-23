import os
import json
import re
from pathlib import Path
from multiprocessing import Pool, cpu_count
from collections import defaultdict


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

INPUT_DIR = PROJECT_ROOT / 'input_label_split'
OUTPUT_DIR = PROJECT_ROOT / 'output_label_split'

MODEL_FOLDERS = ['claude_generated', 'gemini_generated']
CATEGORY_FOLDERS = [
    'classes', 'deinitializers', 'enumCases', 'enums', 'extensions',
    'initializers', 'methods', 'properties', 'protocols', 'structs',
    'subscripts', 'variables'
]


def clean_symbol_name(symbol_name: str) -> str:
    """
    'viewDidLoad(())'나 여러 줄의 시그니처를 제거하고,
    '.deinit' -> 'deinit' 처럼 이름 앞의 점을 제거하여 이름을 정규화합니다.
    """
    cleaned = re.sub(r'\(.*\)', '', symbol_name, flags=re.DOTALL)
    cleaned = cleaned.lstrip('.')
    return cleaned


def extract_selector_name(selector_str: str) -> str | None:
    """'#selector(processData(_:))' -> 'processData' 와 같이 셀렉터에서 순수 함수 이름을 추출합니다."""
    # 중첩된 괄호가 포함된 복잡한 셀렉터(e.g., 클로저)도 처리할 수 있도록 정규식을 수정합니다.
    # 변경 전: r'#selector\(([^)]+)\)'
    # 변경 후: r'#selector\((.*)\)'
    match = re.search(r'#selector\((.*)\)', selector_str)
    if not match:
        return None

    full_selector = match.group(1)
    method_part = full_selector.split('.')[-1]
    return method_part.split('(')[0]


def verify_pair(task_info: tuple):
    """
    하나의 (input, output) 파일 쌍을 검증합니다.
    Input의 모든 필드를 스캔하여 가능한 모든 심벌 이름을 추출하고 비교합니다.
    """
    input_path, output_path = task_info

    try:
        category = input_path.parent.name
        base_name = input_path.stem.replace('input_', '')
        pattern_name = base_name.replace(f'_{category}', '')
    except Exception:
        category = "unknown"
        pattern_name = input_path.stem

    context_str = f"({pattern_name}/{category})"

    if not output_path.exists():
        return (input_path.parent.parent.name, "SKIPPED", f"{context_str} 짝이 되는 Output 파일 없음: {output_path.name}")

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            input_full_data = json.load(f)

        mapping = input_full_data.get('mapping', {})
        input_data = input_full_data.get('data', {})
        input_decisions = input_data.get('decisions', {})

        keys_with_names = {
            mapping.get(key) for key in [
                'references', 'calls_out', 'inherits',
                'conforms', 'extension_of'
            ] if mapping.get(key)
        }
        selector_key = mapping.get('selector_refs')

        all_input_symbols = set()
        for cat_values in input_decisions.values():
            for symbol in cat_values:
                name = symbol.get('symbol_name', '')
                if name:
                    all_input_symbols.add(clean_symbol_name(name))

                symbol_input = symbol.get('input', {})
                for p_key, value in symbol_input.items():
                    if p_key in keys_with_names:
                        if isinstance(value, list):
                            for item in value:
                                all_input_symbols.add(clean_symbol_name(str(item)))
                        elif isinstance(value, str):
                            all_input_symbols.add(clean_symbol_name(value))

                    elif p_key == selector_key and isinstance(value, list):
                        for selector_str in value:
                            extracted_name = extract_selector_name(selector_str)
                            if extracted_name:
                                all_input_symbols.add(extracted_name)

        with open(output_path, 'r', encoding='utf-8') as f:
            output_data = json.load(f)

        all_output_symbols = set()
        for cat_values in output_data.values():
            for symbol in cat_values:
                name = symbol.get('symbol_name')
                if name:
                    all_output_symbols.add(clean_symbol_name(name))

        if all_output_symbols.issubset(all_input_symbols):
            return (input_path.parent.parent.name, "PASS", f"{context_str} 통과")
        else:
            missing_symbols = all_output_symbols - all_input_symbols
            return (
            input_path.parent.parent.name, "FAIL", f"{context_str} Input 문맥에 존재하지 않는 심벌 발견: {list(missing_symbols)}")

    except Exception as e:
        return (input_path.parent.parent.name, "ERROR", f"{context_str} 처리 중 오류: {e}")


def main():
    """메인 실행 함수"""
    tasks = []
    print("검증할 Input/Output 파일 쌍을 검색합니다...")

    for model_folder in MODEL_FOLDERS:
        for category_folder in CATEGORY_FOLDERS:
            input_category_path = INPUT_DIR / model_folder / category_folder
            if not input_category_path.is_dir():
                continue

            for input_file in input_category_path.glob('input_*.json'):
                base_name = input_file.name.replace('input_', 'output_')
                output_file = OUTPUT_DIR / model_folder / category_folder / base_name
                tasks.append((input_file, output_file))

    if not tasks:
        print("검증할 파일을 찾지 못했습니다.")
        return

    print(f"총 {len(tasks)}개의 파일 쌍에 대해 검증을 시작합니다...")

    with Pool(processes=cpu_count()) as pool:
        results = pool.map(verify_pair, tasks)

    summary = defaultdict(lambda: defaultdict(int))
    failed_details = []

    for model, status, message in results:
        summary[model][status] += 1
        if status in ["FAIL", "ERROR"]:
            failed_details.append(f"[{model}] {status}: {message}")

    print("\n\n" + "=" * 50)
    print("📊 검증 결과 요약")
    print("=" * 50)

    grand_total = 0
    for model in MODEL_FOLDERS:
        if model in summary:
            stats = summary[model]
            total = sum(stats.values())
            grand_total += total
            print(f"\n--- 모델: {model} (총 {total}개) ---")
            print(f"  - ✅ PASS: {stats['PASS']}개")
            print(f"  - 🔥 FAIL: {stats['FAIL']}개")
            print(f"  - ⏭️ SKIPPED (Output 없음): {stats['SKIPPED']}개")
            print(f"  - 🚨 ERROR: {stats['ERROR']}개")

    print("\n" + "=" * 50)
    print(f"📈 전체 파일 수: {grand_total}개")
    print("=" * 50)

    if failed_details:
        print("\n\n" + "🔥 실패 및 오류 상세 내역:")
        print("-" * 40)
        for detail in sorted(failed_details):
            print(detail)


if __name__ == '__main__':
    main()