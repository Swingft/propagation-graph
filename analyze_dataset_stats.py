import os
from pathlib import Path


def analyze_directory_stats(target_dir_name: str):
    """
    지정된 디렉토리 구조를 탐색하여 각 모델별 .jsonl 파일의
    총 개수, 평균 크기, 그리고 전체 통계를 계산하고 출력합니다.
    """
    project_root = Path.cwd()

    target_root = project_root / 'jsonl' / target_dir_name

    model_folders = ['claude_generated', 'gemini_generated']

    category_folders = [
        'classes', 'deinitializers', 'enumCases', 'enums', 'extensions',
        'initializers', 'methods', 'properties', 'protocols', 'structs',
        'subscripts', 'variables'
    ]

    print(f"\n\n===== '{target_root}' 디렉토리 분석 시작 =====")
    print("-" * 40)

    if not target_root.is_dir():
        print(f"🔥 오류: 대상 디렉토리를 찾을 수 없습니다: {target_root}")
        return

    stats_by_model = {}
    grand_total_files = 0
    grand_total_size_bytes = 0

    for model in model_folders:
        model_path = target_root / model
        if not model_path.is_dir():
            continue

        total_files = 0
        total_size_bytes = 0

        for category in category_folders:
            category_path = model_path / category
            if not category_path.is_dir():
                continue

            jsonl_files = list(category_path.glob('*.jsonl'))

            total_files += len(jsonl_files)
            for file_path in jsonl_files:
                total_size_bytes += file_path.stat().st_size

        stats_by_model[model] = {
            'count': total_files,
            'total_size': total_size_bytes
        }

        grand_total_files += total_files
        grand_total_size_bytes += total_size_bytes

    print("📊 분석 결과:")
    if not stats_by_model:
        print("분석할 파일을 찾지 못했습니다. 디렉토리 구조를 확인해주세요.")
        return

    for model, stats in stats_by_model.items():
        count = stats['count']
        total_size = stats['total_size']

        if count > 0:
            avg_size_kb = (total_size / count) / 1024
            print(f"  - 모델: {model}")
            print(f"    - 총 파일 개수: {count}개")
            print(f"    - 평균 파일 크기: {avg_size_kb:.2f} KB")
        else:
            print(f"  - 모델: {model}")
            print(f"    - 발견된 파일 없음")
        print("-" * 20)

    print("=" * 40)
    print("📈 전체 요약:")
    if grand_total_files > 0:
        overall_avg_size_kb = (grand_total_size_bytes / grand_total_files) / 1024
        print(f"  - 모든 모델의 총 파일 개수: {grand_total_files}개")
        print(f"  - 전체 평균 파일 크기: {overall_avg_size_kb:.2f} KB")
    else:
        print("  - 처리된 파일이 없습니다.")
    print("=" * 40)


if __name__ == '__main__':
    analyze_directory_stats('input_label_split')
    analyze_directory_stats('output_label_split')
