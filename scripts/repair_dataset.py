import json
import os
from pathlib import Path
from typing import List, Dict, Any
from datasets import load_dataset


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
FINAL_DATASET_FILE = PROJECT_ROOT / "eval.jsonl"
REPAIRED_DATASET_FILE = PROJECT_ROOT / "alpaca_repaired.jsonl"


def fix_broken_jsonl(input_file: Path, output_file: Path) -> int:
    """
    JSONL 파일을 읽어 각 줄의 파싱 오류를 수정하고, 수정된 데이터를 새로운 파일에 씁니다.
    """
    print(f"✅ '{input_file.name}' 파일의 자동 복구를 시작합니다...")
    fixed_records: List[Dict[str, Any]] = []
    issues_found = 0

    with input_file.open('r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
                fixed_records.append(record)

            except json.JSONDecodeError as e:
                issues_found += 1

                # 간단한 자동 수정 시도: 누락된 닫는 문자 추가
                fixed = False
                for fix in ['"', '}', '"}', '"]}', '"]}']:  # 다양한 닫는 문자 조합 시도
                    try:
                        fixed_line = line + fix
                        record = json.loads(fixed_line)
                        fixed_records.append(record)
                        print(f"🔧 줄 {line_num}: '{fix}'를 추가하여 오류를 수정했습니다. (오류: {e})")
                        fixed = True
                        break
                    except json.JSONDecodeError:
                        continue  # 현재 fix_char로 실패하면 다음 fix_char 시도

                if not fixed:
                    print(f"⚠️  줄 {line_num}: 수정할 수 없어 건너뜁니다. (내용: '{line[:75]}...' 오류: {e})")

    if fixed_records:
        with output_file.open('w', encoding='utf-8') as f:
            for record in fixed_records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print("\n--- 복구 요약 ---")
    print(f"🔍 발견된 문제: {issues_found}개")
    print(f"💾 유효한 레코드 저장: {len(fixed_records)}개")
    print(f"✨ 복구된 파일 생성: '{output_file}'")

    return len(fixed_records)


if __name__ == '__main__':
    if not FINAL_DATASET_FILE.exists():
        print(f"❌ 오류: 원본 파일 '{FINAL_DATASET_FILE}'을 찾을 수 없습니다. 데이터 생성 스크립트를 먼저 실행하세요.")
    else:
        record_count = fix_broken_jsonl(FINAL_DATASET_FILE, REPAIRED_DATASET_FILE)

        if record_count > 0:
            print("\n--- 복구된 파일 검증 ---")
            print("🚀 복구된 데이터셋을 로드합니다...")
            try:
                dataset = load_dataset("json", data_files=str(REPAIRED_DATASET_FILE), split="train")
                print(f"🎉 성공! 복구된 데이터셋이 {len(dataset)}개의 레코드로 로드되었습니다.")
            except Exception as e:
                print(f"❌ 검증 실패! 복구된 파일을 로드할 수 없습니다. 오류: {e}")
