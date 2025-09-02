import os
import json
from multiprocessing import Pool, cpu_count

# --- 경로 설정 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
# 처리할 최상위 디렉토리
ROOT_DATA_DIR = os.path.join(PROJECT_ROOT, 'output_label')


def process_file(file_path):
    """
    단일 JSON 파일을 처리하는 함수:
    - 마크다운 코드 블록 제거
    - 지정된 모든 상위 키 목록을 확인하여 'rationale' 키를 재귀적으로 삭제
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 양 끝의 ```json, ``` 제거
        if content.strip().startswith("```json"):
            content = content.strip()[7:]
        if content.strip().endswith("```"):
            content = content.strip()[:-3]

        data = json.loads(content)

        # 'rationale'을 삭제할 대상이 되는 모든 상위 키 목록
        possible_keys = [
            'classes', 'structs', 'enums', 'protocols', 'extensions',
            'methods', 'properties', 'variables', 'enumCases',
            'initializers', 'deinitializers', 'subscripts'
        ]

        # 모든 대상 키를 순회하며 'rationale' 삭제
        for key in possible_keys:
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict) and 'rationale' in item:
                        del item['rationale']

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return f"✅ {os.path.basename(file_path)} - 처리 완료"

    except Exception as e:
        return f"❌ {os.path.basename(file_path)} - 오류 발생: {e}"


def main():
    """
    메인 함수: 대상 디렉토리와 그 하위의 모든 JSON 파일을 찾아 병렬로 처리합니다.
    """
    # ⬇️ 'output_label' 폴더가 있는지 먼저 확인합니다. ⬇️
    if not os.path.isdir(ROOT_DATA_DIR):
        print(f"오류: 대상 디렉토리 '{ROOT_DATA_DIR}'를 찾을 수 없습니다. 경로를 확인해주세요.")
        return

    file_paths = []
    # ⬇️ os.walk를 사용하여 ROOT_DATA_DIR와 그 모든 하위 폴더를 탐색합니다. ⬇️
    for root, _, files in os.walk(ROOT_DATA_DIR):
        for filename in files:
            if filename.endswith('.json'):
                file_paths.append(os.path.join(root, filename))

    if not file_paths:
        print(f"'{ROOT_DATA_DIR}' 디렉토리에서 처리할 JSON 파일을 찾을 수 없습니다.")
        return

    print(f"총 {len(file_paths)}개의 파일을 처리합니다...")

    # 사용 가능한 모든 CPU 코어를 사용하여 병렬 처리
    with Pool(processes=cpu_count()) as pool:
        # tqdm을 사용하려면: from tqdm import tqdm; results = list(tqdm(pool.imap(process_file, file_paths), total=len(file_paths)))
        results = pool.map(process_file, file_paths)
        for result in results:
            print(result)

    print("\n모든 작업이 완료되었습니다. 🎉")


if __name__ == '__main__':
    main()