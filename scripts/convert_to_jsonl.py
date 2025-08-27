import json
import multiprocessing
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

PROCESSING_TASKS = [
    {
        'input': PROJECT_ROOT / 'output_label_split',
        'output': PROJECT_ROOT / 'jsonl/output_label_split'
    },
    {
        'input': PROJECT_ROOT / 'input_label_split',
        'output': PROJECT_ROOT / 'jsonl/input_label_split'
    }
]
TARGET_FOLDERS = ['claude_generated', 'gemini_generated']


def convert_json_to_jsonl(task_info: tuple):
    """
    .json 파일을 .jsonl로 변환합니다.
    - input 파일의 경우, mapping 정보를 meta 데이터에 포함시킵니다.
    """
    source_json_path, input_root, output_root = task_info
    try:
        relative_path = source_json_path.relative_to(input_root)
        output_dir = output_root / relative_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        output_jsonl_path = output_dir / f"{source_json_path.stem}.jsonl"

        with open(source_json_path, 'r', encoding='utf-8') as f:
            full_data = json.load(f)

        lines_to_write = []
        symbol_container = None

        if 'data' in full_data and 'decisions' in full_data.get('data', {}):
            # Input 파일 구조 처리
            data_to_process = full_data['data']
            meta_for_jsonl = data_to_process.get('meta', {}).copy()
            if 'mapping' in full_data:
                meta_for_jsonl['mapping'] = full_data['mapping']
            if meta_for_jsonl:
                lines_to_write.append(json.dumps({'meta': meta_for_jsonl}, ensure_ascii=False))
            symbol_container = data_to_process.get('decisions', {})
        else:
            # Output 파일 구조 처리
            symbol_container = full_data

        if isinstance(symbol_container, dict):
            for category, symbols in symbol_container.items():
                if isinstance(symbols, list):
                    for symbol in symbols:
                        if isinstance(symbol, dict):
                            symbol_copy = symbol.copy()
                            symbol_copy['category'] = category
                            lines_to_write.append(json.dumps(symbol_copy, ensure_ascii=False))

        if not lines_to_write:
            return (str(source_json_path), True, "성공 (내용 없음)")

        with open(output_jsonl_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines_to_write))

        has_meta = lines_to_write and 'meta' in lines_to_write[0]
        symbol_count = len(lines_to_write) - 1 if has_meta else len(lines_to_write)
        return (str(source_json_path), True, f"성공 (총 {symbol_count}개 심벌)")

    except Exception as e:
        return (str(source_json_path), False, f"오류: {e}")


def main():
    """메인 실행 함수"""
    all_files_to_process = []

    print("파일 검색 중...")
    for task in PROCESSING_TASKS:
        input_root = task['input']
        output_root = task['output']

        print(f"'{input_root}' 디렉토리 처리 중...")

        for model_folder in TARGET_FOLDERS:
            model_path = input_root / model_folder
            if not model_path.is_dir():
                continue

            # 'methods_group', 'classes_group' 등 모든 하위 디렉토리를 동적으로 순회
            for group_dir in model_path.iterdir():
                if not group_dir.is_dir():
                    continue

                # 해당 디렉토리 내의 모든 .json 파일을 찾음
                found_files = list(group_dir.glob('*.json'))
                for file_path in found_files:
                    all_files_to_process.append((file_path, input_root, output_root))

    if not all_files_to_process:
        print("작업할 .json 파일을 찾지 못했습니다.")
        return

    print(f"\n총 {len(all_files_to_process)}개의 .json 파일을 .jsonl로 변환합니다.")

    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = pool.map(convert_json_to_jsonl, all_files_to_process)

    success_count = sum(1 for _, success, _ in results if success)
    print(f"\n모든 변환 작업이 완료되었습니다. (성공: {success_count}/{len(results)})")

    failed_files = [res for res in results if not res[1]]
    if failed_files:
        print("\n--- 실패한 파일 목록 ---")
        for path, _, message in failed_files:
            print(f"- {path}\n  {message}")


if __name__ == '__main__':
    main()