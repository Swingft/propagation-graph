import os
import json

INPUT_DIR = 'input_label'
OUTPUT_ROOT_DIR = 'output_label'
TARGET_SUB_DIRS = ['gpt_generated', 'claude_generated', 'gemini_generated']

POSSIBLE_KEYS = [
    'classes', 'structs', 'enums', 'protocols', 'extensions',
    'methods', 'properties', 'variables', 'enumCases',
    'initializers', 'deinitializers', 'subscripts'
]


def get_non_empty_keys(file_path):
    """
    JSON 파일을 읽어, 비어있지 않은 리스트를 값으로 가지는 키(key)들의 집합(set)을 반환합니다.
    파일이 없거나 JSON 파싱에 실패하면 빈 집합을 반환합니다.
    """
    if not os.path.exists(file_path):
        return None

    keys = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'decisions' in data and isinstance(data['decisions'], dict):
            data = data['decisions']

        for key in POSSIBLE_KEYS:
            # 키가 존재하고, 그 값이 비어있지 않은 리스트인 경우 추가
            if key in data and isinstance(data[key], list) and data[key]:
                keys.add(key)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"⚠️ 경고: '{file_path}' 파일을 처리하는 중 오류 발생: {e}")
        return set()

    return keys


def investigate_label_mismatches():
    """
    입력과 정답 레이블 간의 카테고리 불일치 사례를 조사하여 보고합니다.
    """
    print("데이터 정합성 검사를 시작합니다...\n")
    mismatched_files = []

    for sub_dir in TARGET_SUB_DIRS:
        output_dir_path = os.path.join(OUTPUT_ROOT_DIR, sub_dir)
        if not os.path.isdir(output_dir_path):
            continue

        print(f"--- '{output_dir_path}' 디렉토리 검사 중 ---")

        for filename in os.listdir(output_dir_path):
            if not filename.endswith('.json'):
                continue

            output_file_path = os.path.join(output_dir_path, filename)
            input_file_path = os.path.join(INPUT_DIR, filename)

            input_keys = get_non_empty_keys(input_file_path)
            output_keys = get_non_empty_keys(output_file_path)

            if input_keys is None:
                print(f"❓ 건너뜀: 정답 파일 '{output_file_path}'에 해당하는 입력 파일이 없습니다.")
                continue

            unexpected_keys = output_keys - input_keys

            if unexpected_keys:
                mismatched_files.append({
                    "file": output_file_path,
                    "unexpected_keys": sorted(list(unexpected_keys)),
                    "input_keys": sorted(list(input_keys)),
                    "output_keys": sorted(list(output_keys))
                })

    print("\n--- 📜 검사 결과 ---")
    if not mismatched_files:
        print("✅ 모든 파일에서 카테고리 불일치가 발견되지 않았습니다. 데이터가 정합합니다!")
    else:
        print(f"🚨 총 {len(mismatched_files)}개 파일에서 카테고리 불일치가 발견되었습니다:\n")
        for item in mismatched_files:
            print(f"  - 파일: {item['file']}")
            print(f"    - 원인: 입력에 없던 '{', '.join(item['unexpected_keys'])}' 카테고리가 정답에 추가됨")
            print(f"    - 입력 키: {item['input_keys']}")
            print(f"    - 정답 키: {item['output_keys']}\n")


if __name__ == '__main__':
    investigate_label_mismatches()