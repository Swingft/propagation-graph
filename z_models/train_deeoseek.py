import os
import shutil
import warnings
from typing import Optional

import torch
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from trl import SFTTrainer, SFTConfig
from peft import LoraConfig, TaskType

# =========================
# 0) 환경 / 토큰
# =========================
HF_TOKEN: Optional[str] = os.environ.get("HF_TOKEN")

os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
warnings.filterwarnings("ignore", category=UserWarning)

try:
    torch.set_float32_matmul_precision("high")
except Exception:
    pass

# =========================
# 1) 하이퍼파라미터
# =========================
EPOCHS = 3
LR = 2e-4
TRAIN_BS = 1
GRAD_ACCUM = 16
EVAL_BS = 1
PACKING = True
LOG_STEPS = 10
EVAL_STEPS = 50
SAVE_STEPS = 100
SEED = 42
MAX_LENGTH = 4096

USE_LORA = True
LORA_R = 64
LORA_ALPHA = 64
LORA_DROPOUT = 0.1
# ▼▼▼ LoRA 타겟 모듈을 모든 선형 레이어로 확장 ▼▼▼
LORA_TARGETS = "q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj"

# =========================
# 2) 경로/모델
# =========================
MODEL_ID = "deepseek-ai/deepseek-coder-6.7b-instruct"

TRAIN_JSONL = "./train.jsonl"
EVAL_JSONL = ""
OUTPUT_DIR = f"./out/{MODEL_ID.split('/')[-1]}_finetuned"

DEVICE_MAP = "auto"

# =========================
# 3) 허깅페이스 로그인
# =========================
if HF_TOKEN:
    try:
        from huggingface_hub import login as hf_login

        hf_login(token=HF_TOKEN.strip())
        print("✅ HF 로그인 완료")
    except Exception as e:
        print(f"⚠️ HF 로그인 실패(무시): {e}")


# =========================
# 4) 데이터 로더
# =========================
def load_and_prepare_jsonl(train_path: str, eval_path: Optional[str], text_field: str = "text"):
    if not os.path.exists(train_path):
        raise FileNotFoundError(f"학습 파일 없음: {train_path}")

    data_files = {"train": train_path}
    if eval_path:
        if not os.path.exists(eval_path):
            raise FileNotFoundError(f"평가 파일 없음: {eval_path}")
        data_files["validation"] = eval_path

    ds = load_dataset("json", data_files=data_files)
    tr = ds["train"];
    ev = ds.get("validation")

    cols = set(tr.column_names)
    if not ({"instruction", "output"}.issubset(cols) or {"input", "output"}.issubset(cols)):
        raise ValueError(f"데이터 컬럼이 맞지 않습니다. 실제 컬럼: {tr.column_names}")

    def to_text(ex):
        instr = (ex.get("instruction") or "").strip()
        inp = (ex.get("input") or "").strip()
        out = (ex.get("output") or "").strip()

        if not instr and inp:
            instr, inp = inp, ""
        if not instr or not out:
            return None

        prompt = f"### Instruction:\n{instr}\n\n"
        if inp:
            prompt += f"### Input:\n{inp}\n\n"
        prompt += f"### Response:\n{out}"
        return {text_field: prompt}

    tr = tr.map(to_text, remove_columns=tr.column_names).filter(lambda x: x is not None)
    if ev is not None:
        ev = ev.map(to_text, remove_columns=ev.column_names).filter(lambda x: x is not None)

    return tr, ev


# =========================
# 5) 메인 함수
# =========================
def main():
    try:
        from huggingface_hub import HfApi
        HfApi().model_info(MODEL_ID, token=HF_TOKEN)
    except Exception as e:
        raise RuntimeError(f"모델 리포 확인 실패: {MODEL_ID}\n원인: {e}")

    try:
        import random, numpy as np
        random.seed(SEED);
        np.random.seed(SEED);
        torch.manual_seed(SEED)
        if torch.cuda.is_available(): torch.cuda.manual_seed_all(SEED)
    except Exception:
        pass

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("\n" + "=" * 20 + " RUN " + "=" * 20)
    print(f"Model:       {MODEL_ID}")
    print(f"Train JSONL: {TRAIN_JSONL}")
    print(f"Output Dir:  {OUTPUT_DIR}")
    print(f"LoRA:        r={LORA_R}, alpha={LORA_ALPHA}")
    print("=" * 45 + "\n")

    tok = AutoTokenizer.from_pretrained(MODEL_ID, use_fast=True, trust_remote_code=True, token=HF_TOKEN)
    if tok.pad_token is None: tok.pad_token = tok.eos_token

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map=DEVICE_MAP,
        trust_remote_code=True,
        token=HF_TOKEN,
    )

    try:
        model.gradient_checkpointing_enable()
    except Exception:
        pass
    try:
        model.config.attn_implementation = "flash_attention_2"
    except Exception:
        pass
    print("✅ 모델/토크나이저 로드 완료 (4-bit Quantization 적용)")

    train_ds, eval_ds = load_and_prepare_jsonl(TRAIN_JSONL, EVAL_JSONL or None)
    print("✅ 데이터 준비 완료")

    cfg = dict(
        output_dir=OUTPUT_DIR,
        dataset_text_field="text",
        packing=PACKING,
        # max_seq_length=MAX_LENGTH,
        per_device_train_batch_size=TRAIN_BS,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LR,
        num_train_epochs=EPOCHS,
        logging_steps=LOG_STEPS,
        save_strategy="steps",
        save_steps=SAVE_STEPS,
        seed=SEED,
        report_to=[],
        gradient_checkpointing=True,
        optim="paged_adamw_32bit",
        bf16=True,
    )
    if eval_ds is not None:
        cfg.update({
            "per_device_eval_batch_size": EVAL_BS,
            "eval_strategy": "steps",
            "eval_steps": EVAL_STEPS,
        })
    sft_config = SFTConfig(**cfg)

    peft_cfg = None
    if USE_LORA:
        targets = [t.strip() for t in LORA_TARGETS.split(",") if t.strip()]
        peft_cfg = LoraConfig(
            r=LORA_R, lora_alpha=LORA_ALPHA, lora_dropout=LORA_DROPOUT,
            bias="none", task_type=TaskType.CAUSAL_LM, target_modules=targets
        )
        print(f"✅ LoRA 적용(r={LORA_R}, alpha={LORA_ALPHA})")

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        # tokenizer=tok,
        peft_config=peft_cfg,
    )

    print("🚀 훈련을 시작합니다...")
    trainer.train()

    print("\nLoRA 어댑터를 베이스 모델에 병합 후 저장합니다...")
    merged_model = trainer.model.merge_and_unload()
    merged_model.save_pretrained(OUTPUT_DIR)
    tok.save_pretrained(OUTPUT_DIR)
    print(f"✅ 병합된 전체 모델이 '{OUTPUT_DIR}'에 저장되었습니다.")

    try:
        base = os.path.abspath(OUTPUT_DIR)
        shutil.make_archive(base, "zip", OUTPUT_DIR)
        print(f"✅ ZIP 생성 완료: {OUTPUT_DIR}.zip")
    except Exception:
        pass


if __name__ == "__main__":
    main()