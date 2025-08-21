import itertools
import time
import config

from claude_handler import ClaudeHandler
from gemini_handler import GeminiHandler


def generate_specific_combinations(patterns: list, combination_lengths: list) -> list:
    """
    주어진 리스트에서 특정 개수(예: 1, 2, 3, 4개)의 조합만 생성합니다.
    """
    all_combinations_iterator = itertools.chain.from_iterable(
        itertools.combinations(patterns, r) for r in combination_lengths
    )
    return [list(combo) for combo in all_combinations_iterator]


def main():
    """
    1, 2, 3, 4개 패턴 조합을 생성하고, 각 조합에 대해 AI 모델들을 호출하여
    Swift 코드를 생성하고 저장 및 업로드하는 메인 함수.
    """
    master_patterns = config.OBFUSCATION_EXCLUSION_PATTERNS

    # 전체 조합 대신, 1, 2, 3개로 이루어진 조합만 생성하도록 지정합니다.
    combinations_to_test = [1, 2, 3]
    all_combinations = generate_specific_combinations(master_patterns, combinations_to_test)


    pattern_to_index = {pattern: i + 1 for i, pattern in enumerate(master_patterns)}

    start_index = 0
    STOP_BEFORE = 2
    combinations_to_run = all_combinations[start_index:]

    total_combinations = len(all_combinations)
    print(f"총 {total_combinations}개 ({combinations_to_test}개 조합)의 패턴 조합에 대한 코드 생성을 시작합니다.")

    # 각 조합을 순회하며 AI 모델들을 호출
    for i, current_combination in enumerate(combinations_to_run, start=start_index + 1):

        if i >= STOP_BEFORE:
            print(f"\n⏹️ 요청한 범위까지만 실행 완료: {start_index + 1} ~ {STOP_BEFORE - 1}/{total_combinations}")
            break

        indices = sorted([pattern_to_index[p] for p in current_combination])
        filename_prefix = f"pattern_{'_'.join(map(str, indices))}"
        swift_filename = f"{filename_prefix}.swift"
        prompt_config = config.create_prompt_config(selected_patterns=current_combination)

        print(f"\n--- [{i}/{total_combinations}] 조합 처리 중: {filename_prefix} ---")

        # Claude
        # try:
        #     print(f"🔹 Claude generating for {filename_prefix}...")
        #     claude_reply = ClaudeHandler.ask(prompt_config)
        #     ClaudeHandler.save_and_upload(claude_reply, swift_filename,
        #                                   drive_folder=f"claude_generated/{filename_prefix}")
        # except Exception as e:
        #     print(f"❌ Claude error for {filename_prefix}: {e}")

        # Gemini
        # try:
        #     print(f"🔹 Gemini generating for {filename_prefix}...")
        #     gemini_reply = GeminiHandler.ask(prompt_config, retries=5, base_wait=5)
        #     # 성공했을 때만 저장/업로드
        #     GeminiHandler.save_and_upload(
        #         gemini_reply,
        #         swift_filename,
        #         drive_folder=f"gemini_generated/{filename_prefix}",
        #     )
        #     print(f"✅ {filename_prefix} 완료")
        # except Exception as e:
        #     print(f"❌ Gemini 실패: {e}")
        #     print(f"⏭️ {filename_prefix} 저장/업로드 생략 후 다음으로 진행")

        print(f"--- {filename_prefix} 처리 완료, 2초 대기 ---")
        time.sleep(10)

    print("\n🎉 모든 패턴 조합에 대한 작업이 완료되었습니다.")


if __name__ == "__main__":
    main()