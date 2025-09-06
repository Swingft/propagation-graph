import os
from pathlib import Path
import shutil

# --------------------------------------------------------------------------
# [설정] 정리할 대상 폴더를 지정합니다.
# --------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
# [수정] 새로운 분할된 출력 폴더 경로를 사용합니다.
TARGET_ROOT = PROJECT_ROOT / 'llm_training_data_split' / 'outputs'


def process_and_cleanup_file(file_path: Path):
    """
    파일을 읽어 CoT('<thinking>') 존재 여부에 따라 처리합니다.
    - CoT가 있으면: 불필요한 '''xml 접두사를 제거하고 '수정' 대상으로 표시합니다.
    - CoT가 없으면: '삭제' 대상으로 표시합니다.
    (실제 수정/삭제는 기본적으로 주석 처리되어 있습니다.)
    """
    try:
        # 원본 내용을 그대로 읽음
        original_content = file_path.read_text(encoding='utf-8')

        # 파일이 비어있으면 건너뜀
        if not original_content.strip():
            return 'skipped_empty'

        # '<thinking>' 태그가 파일 내에 존재하는지 확인
        if '<thinking>' in original_content:
            # 앞쪽 공백을 제거한 내용 확인
            stripped_content = original_content.lstrip()

            # 만약 불필요한 마크다운 코드 블록으로 시작한다면
            if stripped_content.startswith("'''xml"):
                print(f"  - [수정 대상] '''xml 접두사가 있는 파일입니다: {file_path.name}")

                # '<thinking>' 태그의 시작 위치를 찾아 그 부분부터 새로운 내용으로 지정
                start_index = original_content.find('<thinking>')
                new_content = original_content[start_index:]

                # --- 실제 파일 수정 로직 ---
                # 아래 줄의 주석('#')을 제거하면 파일이 실제로 수정됩니다.
                # file_path.write_text(new_content, encoding='utf-8')

                print(f"    -> (수정 기능은 현재 주석 처리되어 있습니다)")
                return 'modified'
            else:
                # '<thinking>'은 있지만, 수정할 필요가 없는 정상 파일
                return 'skipped_ok'
        else:
            # '<thinking>' 태그가 아예 없는 파일
            print(f"  - [삭제 대상] CoT가 없는 파일입니다: {file_path.name}")

            # --- 실제 파일 삭제 로직 ---
            # 아래 줄의 주석('#')을 제거하면 파일이 실제로 삭제됩니다.
            file_path.unlink()

            print(f"    -> (삭제 기능은 현재 주석 처리되어 있습니다)")
            return 'to_delete'

    except Exception as e:
        print(f"  - [오류] '{file_path.name}' 처리 중 예외 발생: {e}")
        return 'error'


def main():
    """
    입력 디렉토리에서 CoT가 없거나 형식이 잘못된 파일을 찾아 정리합니다.
    """
    print(f"🔍 정리 대상 디렉토리: {TARGET_ROOT}")
    if not TARGET_ROOT.is_dir():
        print(f"🚨 치명적 오류: 디렉토리가 없습니다: {TARGET_ROOT}")
        return

    print("\nℹ️ 정보: CoT('<thinking>')가 없는 파일은 삭제 대상으로,")
    print("   \"'''xml\"로 시작하는 파일은 수정 대상으로 분류합니다.")
    print("   실제 파일 수정/삭제는 코드에서 주석 처리되어 있으니 안심하세요.")

    # [수정] .txt 대신 .json 파일을 찾도록 변경
    files_to_process = sorted(list(TARGET_ROOT.rglob("output_*.json")))
    if not files_to_process:
        print("\n🤷 처리할 output 파일을 찾지 못했습니다.")
        return

    print(f"\n✨ 총 {len(files_to_process)}개의 파일을 검사합니다.")
    print("-" * 50)

    counts = {'modified': 0, 'to_delete': 0, 'skipped_ok': 0, 'skipped_empty': 0, 'error': 0}

    for file_path in files_to_process:
        result = process_and_cleanup_file(file_path)
        if result in counts:
            counts[result] += 1

    print("-" * 50)
    print("🎉 모든 작업 완료!")
    print("📊 결과 요약:")
    print(f"  - 📝 수정 대상 파일 발견 (실제 수정 안 됨): {counts['modified']}개")
    print(f"  - 🎯 삭제 대상 파일 발견 (실제 삭제 안 됨): {counts['to_delete']}개")
    print(f"  - ✅ 정상/패스 파일: {counts['skipped_ok']}개")
    print(f"  - 텅 빈 파일: {counts['skipped_empty']}개")
    if counts['error'] > 0:
        print(f"  - ❌ 오류 발생: {counts['error']}개")


if __name__ == "__main__":
    main()
