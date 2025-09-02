import subprocess
import sys
import time
import os


def run_script(command_parts):
    """
    지정된 파이썬 스크립트와 파라미터를 실행하고 성공 여부를 반환합니다.
    command_parts: ['스크립트_경로', '파라미터1', '파라미터2', ...] 형태의 리스트
    """
    script_path = command_parts[0]
    script_name = os.path.basename(script_path)

    full_command_str = f"python {' '.join(command_parts)}"

    try:
        print(f"\n{'─' * 20}")
        print(f"🚀 '{full_command_str}' 실행 시작...")
        print(f"{'─' * 20}")

        start_time = time.time()

        command_to_run = [sys.executable] + command_parts

        result = subprocess.run(
            command_to_run,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

        end_time = time.time()
        duration = end_time - start_time

        print(result.stdout)

        print(f"✅ '{script_name}' 실행 완료! (소요 시간: {duration:.2f}초)")
        return True

    except FileNotFoundError:
        print(f"🔥 오류: '{script_name}' 파일을 찾을 수 없습니다. 경로: {script_path}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"🔥 '{full_command_str}' 실행 중 오류 발생!")
        print("\n--- STDOUT ---")
        print(e.stdout)
        print("\n--- STDERR ---")
        print(e.stderr)
        return False
    except Exception as e:
        print(f"🔥 알 수 없는 예외 발생: {e}")
        return False


def main():
    """
    전체 데이터 처리 파이프라인을 순서대로 실행합니다.
    """
    scripts_dir = "scripts"

    pipeline_scripts = [
        # [os.path.join(scripts_dir, "generate_swift_code.py")],
        # [os.path.join(scripts_dir, "generate_input_from_swift_code.py")],
        # [os.path.join(scripts_dir, "generate_output_from_input.py")],
        # [os.path.join(scripts_dir, "clean_output.py")],
        # [os.path.join(scripts_dir, "split_labels_by_category.py")],
        # [os.path.join(scripts_dir, "verify_outputs.py")],
        # [os.path.join(scripts_dir, "convert_to_jsonl.py")],
        # [os.path.join(scripts_dir, "create_dataset.py")],
        # [os.path.join(scripts_dir, "repair_dataset.py")],

        # 모델 변환 및 평가 단계
        [os.path.join(scripts_dir, "convert_to_model_coreml.py"), "info"],
        [os.path.join(scripts_dir, "convert_to_model_coreml.py"), "test"],
        # [os.path.join(scripts_dir, "convert_to_model_coreml.py"), "quantize"],
        # [os.path.join(scripts_dir, "convert_to_model_coreml.py"), "coreml"],
        # [os.path.join(scripts_dir, "evaluate_model.py")],
    ]

    print("====== 전체 데이터 처리 파이프라인 시작 ======")
    total_start_time = time.time()

    for command_parts in pipeline_scripts:
        if not run_script(command_parts):
            script_name = os.path.basename(command_parts[0])
            print(f"\n====== 파이프라인 중단: '{script_name}'에서 오류 발생 ======")
            sys.exit(1)

    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    print(f"\n🎉 ====== 모든 파이프라인 작업 성공적으로 완료! (총 소요 시간: {total_duration:.2f}초) ======")


if __name__ == "__main__":
    main()