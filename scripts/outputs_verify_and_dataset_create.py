import json
import re
from pathlib import Path
from tqdm import tqdm
from typing import Dict, Any, Optional


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

SPLIT_INPUT_ROOT = PROJECT_ROOT / 'llm_training_data_split' / 'inputs'
SPLIT_OUTPUT_ROOT = PROJECT_ROOT / 'llm_training_data_split' / 'outputs'
ALPACA_DATASET_FILE = PROJECT_ROOT / 'swift_obfuscation_dataset.jsonl'
NO_EXCLUSION_OUTPUT = {
    "thinking": "Based on the analysis, no symbols in this context group meet the criteria for obfuscation exclusion.",
    "json_output": {}
}


def parse_and_validate_response(raw_response: str) -> Optional[Dict[str, Any]]:
    """LLM의 원본 응답에서 <thinking>과 JSON을 분리하고 유효성을 검증합니다."""
    try:
        thinking_match = re.search(r"<thinking>(.*?)</thinking>", raw_response, re.DOTALL)
        thinking_content = thinking_match.group(1).strip() if thinking_match else ""

        json_start_index = raw_response.find('{')
        json_end_index = raw_response.rfind('}')

        if json_start_index == -1 or json_end_index == -1:
            return NO_EXCLUSION_OUTPUT

        json_str = raw_response[json_start_index: json_end_index + 1]
        json_output = json.loads(json_str)  # JSON 유효성 검증
        return {"thinking": thinking_content, "json_output": json_output}

    except json.JSONDecodeError:
        return None  # JSON이 깨진 경우 None 반환
    except Exception:
        return None


def main():
    """ 분할된 input/output 쌍을 조합하여 최종 Alpaca .jsonl 파일을 생성합니다. """
    if not SPLIT_INPUT_ROOT.is_dir():
        print(f"🚨 오류: 분할된 입력 디렉토리를 찾을 수 없습니다: {SPLIT_INPUT_ROOT}")
        return

    print("🚀 4단계: 분할된 파일들을 최종 Alpaca 데이터셋으로 통합 시작...")

    input_files = sorted(list(SPLIT_INPUT_ROOT.rglob("*.json")))
    if not input_files:
        print("처리할 분할된 입력 파일이 없습니다.")
        return

    alpaca_records = []
    skipped_files = []

    for input_file_path in tqdm(input_files, desc="Alpaca 레코드 생성 중"):
        try:
            with open(input_file_path, 'r', encoding='utf-8') as f_in:
                input_record = json.load(f_in)

            base_name = input_file_path.stem.replace('input_', '')
            relative_parent = input_file_path.relative_to(SPLIT_INPUT_ROOT).parent
            output_file_path = SPLIT_OUTPUT_ROOT / relative_parent / f"output_{base_name}.json"

            output_content = NO_EXCLUSION_OUTPUT  # Negative 샘플 기본값

            if output_file_path.exists():  # Positive 샘플 처리
                with open(output_file_path, 'r', encoding='utf-8') as f_out:
                    raw_response = f_out.read()

                parsed = parse_and_validate_response(raw_response)
                if parsed is None:
                    skipped_files.append(output_file_path.name)
                    continue  # JSON 검증 실패 시 건너뛰기
                output_content = parsed

            # 최종 Alpaca 레코드 구성
            alpaca_record = {
                "instruction": input_record.get("instruction", ""),
                "input": json.dumps(input_record.get("input", {}), ensure_ascii=False),
                "output": json.dumps(output_content, ensure_ascii=False)
            }
            alpaca_records.append(alpaca_record)

        except Exception as e:
            print(f"\n🚨 오류: {input_file_path.name} 처리 중 오류 발생: {e}")
            continue

    with open(ALPACA_DATASET_FILE, 'w', encoding='utf-8') as f_out:
        for record in alpaca_records:
            f_out.write(json.dumps(record, ensure_ascii=False) + '\n')

    print("\n" + "=" * 50)
    print("🎉 최종 Alpaca 데이터셋 생성 완료!")
    print(f"   - 총 {len(alpaca_records)}개의 레코드가 생성되었습니다.")
    print(f"   - {len(skipped_files)}개의 파일이 깨진 JSON 등의 이유로 건너뛰어졌습니다.")
    print(f"   - 최종 파일: {ALPACA_DATASET_FILE}")
    print("=" * 50)


if __name__ == "__main__":
    main()

