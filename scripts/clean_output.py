import os
import json
from multiprocessing import Pool, cpu_count


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)


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

        return f"{file_path} - 처리 완료"

    except Exception as e:
        return f"{file_path} - 오류 발생: {e}"


def main():
    """
    메인 함수: 대상 디렉토리에서 JSON 파일을 찾아 병렬로 처리합니다.
    """
    # ⬇️ 프로젝트 루트를 기준으로 경로를 설정합니다. ⬇️
    root_dir = os.path.join(PROJECT_ROOT, 'output_label')
    target_dirs = ['claude_generated', 'gemini_generated']
    file_paths = []

    for dir_name in target_dirs:
        path = os.path.join(root_dir, dir_name)
        if os.path.isdir(path):
            for filename in os.listdir(path):
                if filename.endswith('.json'):
                    file_paths.append(os.path.join(path, filename))

    if not file_paths:
        print("처리할 JSON 파일을 찾을 수 없습니다. 디렉토리 구조를 확인해주세요.")
        return

    print(f"총 {len(file_paths)}개의 파일을 처리합니다...")

    with Pool(processes=cpu_count()) as pool:
        results = pool.map(process_file, file_paths)
        for result in results:
            print(result)

    print("\n모든 작업이 완료되었습니다.")


if __name__ == '__main__':
    main()
