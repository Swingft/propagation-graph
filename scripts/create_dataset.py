import json
from pathlib import Path
from tqdm import tqdm


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

SPLIT_DATA_ROOT = PROJECT_ROOT / 'llm_training_data_split'
SPLIT_INPUT_DIR = SPLIT_DATA_ROOT / 'inputs'
SPLIT_OUTPUT_DIR = SPLIT_DATA_ROOT / 'outputs'
ALPACA_DATASET_FILE = PROJECT_ROOT / 'swift_obfuscation_dataset.jsonl'
NO_EXCLUSION_OUTPUT = {
    "thinking": "Based on the analysis, no symbols in this context group meet the criteria for obfuscation exclusion.",
    "json_output": {}
}


def main():
    """분할된 input/output 쌍을 조합하여 최종 Alpaca .jsonl 파일을 생성합니다."""
    if not SPLIT_INPUT_DIR.is_dir():
        print(f"🚨 오류: 분할된 입력 디렉토리를 찾을 수 없습니다: {SPLIT_INPUT_DIR}")
        return

    print(f"🚀 3단계: 분할된 파일들을 최종 Alpaca 데이터셋으로 통합 시작...")

    input_files = sorted(list(SPLIT_INPUT_DIR.rglob("*.json")))
    if not input_files:
        print("처리할 분할된 입력 파일이 없습니다.")
        return

    alpaca_records = []

    for input_file_path in tqdm(input_files, desc="Alpaca 레코드 생성 중"):
        try:
            with open(input_file_path, 'r', encoding='utf-8') as f_in:
                input_record = json.load(f_in)

            base_name = input_file_path.name.replace('input_', '')
            relative_parent = input_file_path.relative_to(SPLIT_INPUT_DIR).parent
            output_file_path = SPLIT_OUTPUT_DIR / relative_parent / f"output_{base_name}"

            output_record = NO_EXCLUSION_OUTPUT  # Negative 샘플 기본값
            if output_file_path.exists():  # Positive 샘플인 경우
                with open(output_file_path, 'r', encoding='utf-8') as f_out:
                    output_record = json.load(f_out)

            # 최종 Alpaca 레코드 구성
            alpaca_record = {
                "instruction": input_record.get("instruction", ""),
                "input": json.dumps(input_record.get("input", {}), ensure_ascii=False),
                "output": json.dumps(output_record, ensure_ascii=False)
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
    print(f"   - 최종 파일: {ALPACA_DATASET_FILE}")
    print("=" * 50)


if __name__ == "__main__":
    main()
