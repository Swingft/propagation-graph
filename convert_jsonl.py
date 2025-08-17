import os
import json
import multiprocessing

ROOT_DIR = 'input_label'
TARGET_FOLDERS = ['claude_generated', 'gemini_generated', 'gpt_generated']
OUTPUT_SUBDIR = 'jsonl_format'


def convert_json_to_jsonl_with_all_info(source_json_path):
    """
    .json 파일을 .jsonl로 변환
    - 첫 줄에는 meta 정보를 저장
    - 이후 각 줄에는 'category' 정보가 추가된 심벌 객체를 저장
    """
    try:
        source_dir = os.path.dirname(source_json_path)
        base_filename = os.path.basename(source_json_path)
        name_without_ext = os.path.splitext(base_filename)[0]
        output_dir = os.path.join(source_dir, OUTPUT_SUBDIR)
        output_jsonl_path = os.path.join(output_dir, f"{name_without_ext}.jsonl")

        with open(source_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        lines_to_write = []

        # 1. meta 정보를 첫 줄로 추가
        if 'meta' in data:
            meta_line_obj = {'meta': data['meta']}
            lines_to_write.append(json.dumps(meta_line_obj, ensure_ascii=False))

        # 2. 'decisions' 객체가 있는지 확인하고, 그 안에서 카테고리 순회
        if 'decisions' in data and isinstance(data['decisions'], dict):
            symbol_container = data['decisions']
            for category, symbols in symbol_container.items():
                if isinstance(symbols, list):
                    for symbol in symbols:
                        if isinstance(symbol, dict):
                            symbol_copy = symbol.copy()
                            symbol_copy['category'] = category
                            lines_to_write.append(json.dumps(symbol_copy, ensure_ascii=False))

        # 3. 수집된 모든 라인을 .jsonl 파일에 쓰기
        with open(output_jsonl_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines_to_write))

        # meta 정보 라인을 제외한 실제 심벌 개수 계산
        symbol_count = max(0, len(lines_to_write) - 1)
        print(f"성공: {source_json_path} -> {output_jsonl_path} (meta + {symbol_count}개 심벌)")

    except Exception as e:
        print(f"오류: {source_json_path} 처리 중 예외 발생 - {e}")


def main():
    files_to_process = []
    for folder in TARGET_FOLDERS:
        target_path = os.path.join(ROOT_DIR, folder)
        if not os.path.isdir(target_path):
            print(f"경고: '{target_path}' 디렉토리를 찾을 수 없습니다.")
            continue

        output_dir = os.path.join(target_path, OUTPUT_SUBDIR)
        os.makedirs(output_dir, exist_ok=True)

        for root, dirs, files in os.walk(target_path):
            if OUTPUT_SUBDIR in dirs:
                dirs.remove(OUTPUT_SUBDIR)

            for file in files:
                if file.endswith('.json'):
                    files_to_process.append(os.path.join(root, file))

    if not files_to_process:
        print("작업할 .json 파일을 찾지 못했습니다.")
        return

    print(f"총 {len(files_to_process)}개의 .json 파일을 .jsonl로 변환합니다.")

    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        pool.map(convert_json_to_jsonl_with_all_info, files_to_process)

    print("\n모든 변환 작업이 완료되었습니다.")


if __name__ == '__main__':
    main()