import os
import json
import shutil
from multiprocessing import Pool, cpu_count

INPUT_ROOT_DIR = 'input_label'
OUTPUT_ROOT_DIR = 'output_label'
MODEL_SUB_DIRS = ['gpt_generated', 'claude_generated', 'gemini_generated']

SPLIT_INPUT_DIR = 'input_label_split'
SPLIT_OUTPUT_ROOT_DIR = 'output_label_split'

POSSIBLE_KEYS = [
    'classes', 'structs', 'enums', 'protocols', 'extensions',
    'methods', 'properties', 'variables', 'enumCases',
    'initializers', 'deinitializers', 'subscripts'
]


def setup_directories():
    """결과를 저장할 디렉토리를 준비합니다."""
    print("결과를 저장할 디렉토리를 초기화합니다...")
    if os.path.exists(SPLIT_INPUT_DIR):
        shutil.rmtree(SPLIT_INPUT_DIR)
    if os.path.exists(SPLIT_OUTPUT_ROOT_DIR):
        shutil.rmtree(SPLIT_OUTPUT_ROOT_DIR)

    for sub_dir in MODEL_SUB_DIRS:
        for key in POSSIBLE_KEYS:
            os.makedirs(os.path.join(SPLIT_INPUT_DIR, sub_dir, key), exist_ok=True)
            os.makedirs(os.path.join(SPLIT_OUTPUT_ROOT_DIR, sub_dir, key), exist_ok=True)
    print("디렉토리 준비 완료.")


def process_file_set(base_filename):
    """
    하나의 기본 파일 이름에 대해 모든 모델 디렉토리를 순회하며 분할 작업을 수행합니다.
    """
    try:
        # 모델별 하위 디렉토리를 순회
        for sub_dir in MODEL_SUB_DIRS:
            # 1. 입력 파일 처리
            input_file_path = os.path.join(INPUT_ROOT_DIR, sub_dir, base_filename)
            if os.path.exists(input_file_path):
                with open(input_file_path, 'r', encoding='utf-8') as f:
                    input_data = json.load(f)

                meta_data = input_data.get('meta', {})
                decisions_data = input_data.get('decisions', {})

                for key in POSSIBLE_KEYS:
                    if key in decisions_data and decisions_data[key]:
                        split_input_data = {"meta": meta_data, "decisions": {key: decisions_data[key]}}
                        new_filename = f"{os.path.splitext(base_filename)[0]}_{key}.json"
                        save_path = os.path.join(SPLIT_INPUT_DIR, sub_dir, key, new_filename)
                        with open(save_path, 'w', encoding='utf-8') as f:
                            json.dump(split_input_data, f, ensure_ascii=False, indent=2)

            # 2. 출력 파일 처리
            output_file_path = os.path.join(OUTPUT_ROOT_DIR, sub_dir, base_filename)
            if os.path.exists(output_file_path):
                with open(output_file_path, 'r', encoding='utf-8') as f:
                    output_data = json.load(f)

                for key in POSSIBLE_KEYS:
                    if key in output_data and output_data[key]:
                        split_output_data = {key: output_data[key]}
                        new_filename = f"{os.path.splitext(base_filename)[0]}_{key}.json"
                        save_path = os.path.join(SPLIT_OUTPUT_ROOT_DIR, sub_dir, key, new_filename)
                        with open(save_path, 'w', encoding='utf-8') as f:
                            json.dump(split_output_data, f, ensure_ascii=False, indent=2)

        return f"✅ '{base_filename}' 파일 세트 처리 완료"
    except Exception as e:
        return f"🔥 '{base_filename}' 처리 중 오류 발생: {e}"


def main():
    """메인 실행 함수"""
    setup_directories()

    # 모든 하위 디렉토리를 탐색하여 고유 파일 목록 수집
    all_base_filenames = set()
    for root_dir in [INPUT_ROOT_DIR, OUTPUT_ROOT_DIR]:
        if not os.path.isdir(root_dir): continue
        for sub_dir in MODEL_SUB_DIRS:
            dir_path = os.path.join(root_dir, sub_dir)
            if not os.path.isdir(dir_path): continue
            for filename in os.listdir(dir_path):
                if filename.endswith('.json'):
                    all_base_filenames.add(filename)

    if not all_base_filenames:
        print("처리할 파일을 찾을 수 없습니다. 디렉토리 구조를 확인해주세요.")
        return

    file_list = sorted(list(all_base_filenames))
    print(f"\n총 {len(file_list)}개의 파일 세트에 대해 분할 작업을 시작합니다...")

    with Pool(processes=cpu_count()) as pool:
        results = pool.map(process_file_set, file_list)
        for res in results:
            print(res)

    print("\n모든 파일 분할 작업이 완료되었습니다.")


if __name__ == '__main__':
    main()