import itertools
import time
import os
import sys
import config
from collections import Counter

from claude_handler import ClaudeHandler
from gemini_handler import GeminiHandler

SCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, 'data')


def generate_specific_combinations(patterns: list, combination_lengths: list) -> list:
    """
    주어진 리스트에서 특정 개수(예: 1, 2, 3개)의 조합만 생성합니다. (itertools.combinations 사용)
    """
    all_combinations_iterator = itertools.chain.from_iterable(
        itertools.combinations(patterns, r) for r in combination_lengths
    )
    return [list(combo) for combo in all_combinations_iterator]


def generate_rotational_combinations(patterns: list, seed_indices: list) -> list:
    """
    씨앗 조합을 1씩 회전시켜 모든 요소가 균등하게 포함된 조합을 생성합니다.
    """
    num_patterns = len(patterns)
    all_combinations = []

    current_indices = list(seed_indices)

    for _ in range(num_patterns):
        combo = [patterns[i] for i in current_indices]
        all_combinations.append(combo)
        current_indices = [(i + 1) % num_patterns for i in current_indices]

    return all_combinations


def main():
    """
    균등한 패턴 조합을 생성하고, 각 패턴의 사용 빈도를 출력한 후,
    AI 모델을 호출하여 Swift 코드를 생성하고 저장하는 메인 함수입니다.
    """

    master_patterns = config.OBFUSCATION_EXCLUSION_PATTERNS

    # --- 1. nC1, nC2, nC3 조합 생성 ---
    combination_lengths = [1]  # 생성하고 싶은 조합의 길이를 리스트로 지정
    print(f"총 {len(master_patterns)}개의 마스터 패턴에서 {combination_lengths}개를 선택하는 모든 조합을 생성합니다.")

    all_combinations_iterator = itertools.chain.from_iterable(
        itertools.combinations(master_patterns, r) for r in combination_lengths
    )
    all_combinations = [list(combo) for combo in all_combinations_iterator]

    # 각 패턴(숫자)별 사용 빈도 계산 및 출력
    print("--- 패턴 사용 빈도 분석 ---")
    flat_list = [pattern for combo in all_combinations for pattern in combo]
    pattern_counts = Counter(flat_list)

    for pattern, count in sorted(pattern_counts.items()):
        print(f"패턴 '{pattern}': {count}번 사용")
    print("---------------------------\n")

    pattern_to_index = {pattern: i + 1 for i, pattern in enumerate(master_patterns)}

    start_index = 0
    STOP_BEFORE = len(all_combinations) + 1

    combinations_to_run = all_combinations[start_index:]

    total_combinations = len(all_combinations)
    print(f"총 {total_combinations}개의 조합에 대한 코드 생성을 시작합니다.")
    print(f"실행 범위: {start_index + 1}번부터 {STOP_BEFORE - 1}번까지")

    for i, current_combination in enumerate(combinations_to_run, start=start_index + 1):
        if i >= STOP_BEFORE:
            print(f"\n⏹️ 중단 지점에 도달하여 실행을 중지합니다: {start_index + 1} ~ {STOP_BEFORE - 1}/{total_combinations}")
            break

        indices = sorted([pattern_to_index[p] for p in current_combination])
        filename_prefix = f"pattern_{'_'.join(map(str, indices))}"
        swift_filename = f"{filename_prefix}.swift"
        prompt_config = config.create_prompt_config(selected_patterns=current_combination)

        print(f"\n--- [{i}/{total_combinations}] 조합 처리 중: {filename_prefix} ---")

        # --- Claude 핸들러 ---
        # try:
        #     # Claude 출력 경로 및 파일 존재 여부 확인
        #     claude_output_dir = os.path.join(OUTPUT_ROOT, 'claude_generated')
        #     claude_filepath = os.path.join(claude_output_dir, swift_filename)
        #
        #     if os.path.exists(claude_filepath):
        #         print(f"⏭️  건너뛰기 (Claude): 이미 파일이 존재합니다: {swift_filename}")
        #     else:
        #         print(f"🔹 Claude로 {filename_prefix} 생성 중...")
        #         claude_reply = ClaudeHandler.ask(prompt_config)
        #         ClaudeHandler.save_and_upload(claude_reply, swift_filename,
        #                                       drive_folder=f"claude_generated",
        #                                       local_dir=claude_output_dir)
        # except Exception as e:
        #     print(f"❌ {filename_prefix}에 대한 Claude 처리 오류: {e}")

        # --- Gemini 핸들러 ---
        # try:
        #     # Gemini 출력 경로 및 파일 존재 여부 확인
        #     gemini_output_dir = os.path.join(OUTPUT_ROOT, 'gemini_generated')
        #     gemini_filepath = os.path.join(gemini_output_dir, swift_filename)
        #
        #     if os.path.exists(gemini_filepath):
        #         print(f"⏭️  건너뛰기 (Gemini): 이미 파일이 존재합니다: {swift_filename}")
        #     else:
        #         print(f"🔹 Gemini로 {filename_prefix} 생성 중...")
        #         gemini_reply = GeminiHandler.ask(prompt_config, retries=5, base_wait=5)
        #         GeminiHandler.save_and_upload(gemini_reply, swift_filename,
        #                                       drive_folder=f"gemini_generated",
        #                                       local_dir=gemini_output_dir)
        #         print(f"✅ {filename_prefix} 완료")
        # except Exception as e:
        #     print(f"❌ Gemini 실패: {e}")
        #     print(f"⏭️ {filename_prefix} 저장/업로드 생략 후 다음으로 진행")

        print(f"--- {filename_prefix} 처리 완료, 10초 대기 ---")
        time.sleep(10)

    print("\n🎉 모든 패턴 조합에 대한 작업이 완료되었습니다.")


if __name__ == "__main__":
    main()
