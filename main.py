import itertools
import time
import config

# 모든 핸들러를 import 합니다.
from gpt_handler import GPTHandler
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

    # 64번째 조합부터 시작 (Python 인덱스는 0부터 시작하므로 63)
    start_index = 63
    combinations_to_run = all_combinations[start_index:]

    total_combinations = len(all_combinations)
    print(f"총 {total_combinations}개 ({combinations_to_test}개 조합)의 패턴 조합에 대한 코드 생성을 시작합니다.")

    # 각 조합을 순회하며 AI 모델들을 호출합니다.
    # enumerate의 시작 번호를 1로 설정하여 로그를 1부터 표시합니다.
    for i, current_combination in enumerate(combinations_to_run, start=start_index + 1):

        indices = sorted([pattern_to_index[p] for p in current_combination])
        filename_prefix = f"pattern_{'_'.join(map(str, indices))}"
        swift_filename = f"{filename_prefix}.swift"
        prompt_config = config.create_prompt_config(selected_patterns=current_combination)

        print(f"\n--- [{i}/{total_combinations}] 조합 처리 중: {filename_prefix} ---")

        # GPT
        # try:
        #     print(f"🔹 GPT generating for {filename_prefix}...")
        #     gpt_reply = GPTHandler.ask(prompt_config)
        #     GPTHandler.save_and_upload(gpt_reply, swift_filename, drive_folder=f"gpt_generated/{filename_prefix}")
        # except Exception as e:
        #     print(f"❌ GPT error for {filename_prefix}: {e}")

        # Claude
        # try:
        #     print(f"🔹 Claude generating for {filename_prefix}...")
        #     claude_reply = ClaudeHandler.ask(prompt_config)
        #     ClaudeHandler.save_and_upload(claude_reply, swift_filename,
        #                                   drive_folder=f"claude_generated/{filename_prefix}")
        # except Exception as e:
        #     print(f"❌ Claude error for {filename_prefix}: {e}")

        # Gemini
        try:
            print(f"🔹 Gemini generating for {filename_prefix}...")
            gemini_reply = GeminiHandler.ask(prompt_config)
            GeminiHandler.save_and_upload(gemini_reply, swift_filename,
                                          drive_folder=f"gemini_generated/{filename_prefix}")
        except Exception as e:
            print(f"❌ Gemini error for {filename_prefix}: {e}")

        print(f"--- {filename_prefix} 처리 완료, 2초 대기 ---")
        time.sleep(2)

    print("\n🎉 모든 패턴 조합에 대한 작업이 완료되었습니다.")


if __name__ == "__main__":
    main()