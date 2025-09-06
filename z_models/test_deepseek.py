import os
import json
import warnings
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig


MODEL_PATH = "./out/deepseek-coder-6.7b-instruct_finetuned"

# CUDA GPU 사용 가능 여부 확인
if torch.cuda.is_available():
    device = "cuda"
    print(f"✅ NVIDIA GPU 사용 가능: {torch.cuda.get_device_name(0)}")
else:
    device = "cpu"
    print("⚠️ GPU 사용 불가, CPU로 실행됩니다. (매우 느림)")

DTYPE = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.get_device_capability()[0] >= 8 else torch.float32
print(f"사용 정밀도(Compute Dtype): {DTYPE}")

os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
warnings.filterwarnings("ignore", category=UserWarning)

NUM_TESTS = 1  # <<<--- 테스트할 개수를 여기서 직접 수정

TEST_DATA_PATH = "./input.jsonl"
lines_to_test = []

try:
    with open(TEST_DATA_PATH, 'r', encoding='utf-8') as f:
        lines_to_test = [f.readline() for _ in range(NUM_TESTS)]
        lines_to_test = [line for line in lines_to_test if line]

    if not lines_to_test:
        print(f"❌ 오류: '{TEST_DATA_PATH}' 파일에서 데이터를 읽을 수 없거나 파일이 비어 있습니다.")
        exit()

    print(f"✅ 테스트 데이터 로드 완료: {len(lines_to_test)}개 라인을 테스트합니다.")

except FileNotFoundError:
    print(f"❌ 오류: '{TEST_DATA_PATH}' 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
    exit()


def run_inference(test_lines):
    print(f"🚀 모델을 로딩합니다... (경로: {MODEL_PATH})")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=DTYPE,
            bnb_4bit_use_double_quant=True,
        )

        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )

        try:
            model.config.attn_implementation = "flash_attention_2"
        except Exception:
            pass

    except OSError:
        print(f"❌ 오류: '{MODEL_PATH}' 경로에서 모델을 찾을 수 없습니다.")
        return

    model.eval()
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    print("✅ 모델 로딩 완료!")

    for i, line in enumerate(test_lines):
        print("\n" + "=" * 25 + f" [테스트 {i + 1}/{len(test_lines)}] " + "=" * 25)

        data = json.loads(line)
        instruction = data.get("instruction", "")
        input_text = data.get("input", "")

        prompt = (
            "You are an AI programming assistant, utilizing the Deepseek Coder model, "
            "developed by Deepseek Company. Follow the user's instructions carefully and precisely.\n"
            f"### Instruction:\n{instruction}\n\n"
        )
        if input_text:
            prompt += f"### Input:\n{input_text}\n\n"
        prompt += "### Response:"

        print("▶️  모델에 입력될 최종 프롬프트 (일부):")
        print(prompt[:500] + "...")

        inputs = tokenizer(prompt, return_tensors="pt", return_attention_mask=True)

        with torch.no_grad():
            print("\n💬 모델 응답을 생성 중입니다...")
            outputs = model.generate(
                **inputs.to(device),
                max_new_tokens=8192,
                temperature=0.1,
                top_p=0.9,
                do_sample=True,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.pad_token_id,
            )

        response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

        print("\n" + "-" * 20 + " 모델 생성 결과 " + "-" * 20)
        print(response)
        print("-" * 55)


if __name__ == "__main__":
    if lines_to_test:
        run_inference(lines_to_test)