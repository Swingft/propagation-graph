import shutil
from pathlib import Path


def organize_swift_files():
    """
    생성된 Swift 파일들을 소스 폴더(모델) 및 파일명을 기준으로 nCr 규칙에 따라
    새로운 'nCr_organized' 폴더에 분류하여 복사합니다.
    """

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    output_root = project_root / 'data'

    dest_root = project_root / 'nCr_organized'
    dest_root.mkdir(exist_ok=True)

    print(f"🚀 파일 분류를 시작합니다. 대상 폴더: '{dest_root}'")

    # 스캔할 소스 디렉토리 목록 (모델 폴더명)
    source_folders = [
        'claude_generated',
        'gemini_generated',
    ]

    total_copied_count = 0

    # 각 소스 폴더(모델)를 순회
    for folder in source_folders:
        source_dir = output_root / folder
        if not source_dir.exists():
            print(f"⏭️  '{source_dir}' 폴더가 없어 건너뜁니다.")
            continue

        print(f"\n--- 📂 '{source_dir}' 폴더를 스캔 중입니다... ---")

        # 'pattern_*.swift' 형태의 모든 스위프트 파일을 찾음
        for file_path in source_dir.glob("pattern_*.swift"):
            filename = file_path.name

            # 파일명에서 'pattern_'과 '.swift'를 제거하여 인덱스 부분만 추출
            # 예: 'pattern_1_5_19.swift' -> '1_5_19'
            indices_part = file_path.stem.replace("pattern_", "")

            # '_'를 기준으로 분리하여 조합 개수(r)를 계산
            # 예: '1_5_19' -> ['1', '5', '19'] -> 길이 3
            r_value = len(indices_part.split('_'))

            # [수정] 모델별로 폴더를 구분하여 목적지 경로를 설정합니다.
            # 예: 'claude_generated' 폴더의 r=3 파일 -> 'nCr_organized/claude_generated/nC3'
            dest_model_dir = dest_root / folder
            dest_subdir = dest_model_dir / f"nC{r_value}"
            dest_subdir.mkdir(parents=True, exist_ok=True)

            # 최종 파일 경로
            dest_file_path = dest_subdir / filename

            # 파일 복사
            try:
                shutil.copy2(file_path, dest_file_path)
                # [수정] 출력 메시지를 더 명확하게 변경
                print(f"  ✅ 복사 완료: '{filename}'  ->  '{dest_model_dir.name}/{dest_subdir.name}/'")
                total_copied_count += 1
            except Exception as e:
                print(f"  ❌ 복사 실패: '{filename}' 처리 중 오류 발생 - {e}")

    print(f"\n🎉 작업 완료! 총 {total_copied_count}개의 파일을 성공적으로 분류했습니다.")
    print(f"결과는 '{dest_root}' 폴더에서 모델별로 구분되어 저장되었습니다.")


if __name__ == "__main__":
    organize_swift_files()
