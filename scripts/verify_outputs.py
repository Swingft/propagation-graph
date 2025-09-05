import json
import re
from pathlib import Path
from tqdm import tqdm
from typing import Dict, Any, Optional

# --- 경로 상수 ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

INPUT_DATA_ROOT = PROJECT_ROOT / 'llm_training_inputs'
RAW_OUTPUT_ROOT = PROJECT_ROOT / 'llm_training_raw_outputs'
VALIDATED_DATA_ROOT = PROJECT_ROOT / 'llm_training_data_validated'


def parse_and_validate_response(raw_response: str) -> Optional[Dict[str, Any]]:
    """LLM의 원본 응답에서 <thinking>과 JSON을 분리하고 유효성을 검증합니다."""
    try:
        thinking_match = re.search(r"<thinking>(.*?)</thinking>", raw_response, re.DOTALL)
        thinking_content = thinking_match.group(1).strip() if thinking_match else ""

        json_start_index = raw_response.find('{')
        json_end_index = raw_response.rfind('}')

        if json_start_index == -1 or json_end_index == -1:
            return {"thinking": thinking_content or "No JSON block found.", "json_output": {}}

        json_str = raw_response[json_start_index: json_end_index + 1]
        json_output = json.loads(json_str)
        return {"thinking": thinking_content, "json_output": json_output}

    except json.JSONDecodeError:
        return None  # JSON이 깨진 경우 None 반환
    except Exception:
        return None


def main():
    """ "문제지"와 "원본 답안지"를 조합하여 검증된 중간 데이터셋을 생성합니다. """
    if not INPUT_DATA_ROOT.is_dir() or not RAW_OUTPUT_ROOT.is_dir():
        print(f"🚨 오류: 필수 디렉토리를 찾을 수 없습니다.")
        return

    VALIDATED_DATA_ROOT.mkdir(exist_ok=True)
    print("🚀 1단계: API 응답 파싱 및 검증 시작...")

    input_files = sorted(list(INPUT_DATA_ROOT.rglob("*.json")))

    processed_count = 0
    skipped_missing_raw = 0
    skipped_parse_fail = 0
    skipped_already_exists = 0

    for input_file_path in tqdm(input_files, desc="파싱 및 검증 중"):
        try:
            # 짝이 맞는 raw_output 파일 경로 생성
            original_stem = input_file_path.stem.replace('training_input_', '')
            relative_path = input_file_path.relative_to(INPUT_DATA_ROOT)
            raw_output_path = (RAW_OUTPUT_ROOT / relative_path.parent / f"raw_output_{original_stem}.txt")

            # 최종 파일 경로 생성
            validated_output_dir = VALIDATED_DATA_ROOT / relative_path.parent
            validated_output_path = validated_output_dir / f"validated_{original_stem}.json"

            # 각 건너뛰기 조건을 명확하게 분리하고 카운트
            if not raw_output_path.exists():
                skipped_missing_raw += 1
                continue

            if validated_output_path.exists():
                skipped_already_exists += 1
                processed_count += 1  # 이미 처리된 것도 성공으로 간주
                continue

            # 실제 처리 로직
            with open(input_file_path, 'r', encoding='utf-8') as f_in:
                input_data = json.load(f_in)

            with open(raw_output_path, 'r', encoding='utf-8') as f_raw:
                raw_response = f_raw.read()

            parsed_output = parse_and_validate_response(raw_response)

            if parsed_output is None:
                # print(f"\n⚠️ 경고: {raw_output_path.name} 파싱 실패. 건너뜁니다.")
                skipped_parse_fail += 1
                continue

            validated_data = {
                "instruction": input_data.get("instruction", ""),
                "input": input_data.get("input", {}),
                "output": parsed_output
            }

            validated_output_dir.mkdir(parents=True, exist_ok=True)
            with open(validated_output_path, 'w', encoding='utf-8') as f_out:
                json.dump(validated_data, f_out, indent=2, ensure_ascii=False)

            processed_count += 1

        except Exception as e:
            # 예상치 못한 오류가 발생하면 파싱 실패로 간주
            skipped_parse_fail += 1
            # print(f"\n🚨 오류: {input_file_path.name} 처리 중 오류 발생: {e}")
            continue

    print("\n" + "=" * 50)
    print("🎉 1단계 완료! 최종 결과 요약:")
    print("=" * 50)
    print(f"  - 📂 총 확인한 입력 파일: {len(input_files)}개")
    print("-" * 50)
    print(f"  - ✅ 성공적으로 검증/처리된 파일: {processed_count}개")
    print(f"     (이 중 이미 처리되어 건너뛴 파일: {skipped_already_exists}개)")
    print("-" * 50)
    print(f"  - ⏭️ 건너뛴 파일 (총 {skipped_missing_raw + skipped_parse_fail}개):")
    print(f"     - 원본 응답(.txt) 파일 없음: {skipped_missing_raw}개")
    print(f"     - 파싱/검증 실패: {skipped_parse_fail}개")
    print("=" * 50)


if __name__ == "__main__":
    main()

