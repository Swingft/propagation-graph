import os
import shutil
import warnings
from typing import Optional

import torch
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
from trl import SFTTrainer, SFTConfig
# ▼▼▼ .env 파일을 로드하기 위한 라이브러리 임포트 ▼▼▼
from pathlib import Path
from dotenv import load_dotenv


env_path = Path(__file__).resolve().parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"✅ .env 파일 로드 완료: {env_path}")
else:
    print(f"⚠️ .env 파일을 찾을 수 없습니다: {env_path}")

HF_TOKEN: Optional[str] = os.environ.get("HF_TOKEN")

os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
warnings.filterwarnings("ignore", category=UserWarning)

try:
    torch.set_float32_matmul_precision("high")
except Exception:
    pass

EPOCHS        = 3
LR            = 2e-4
TRAIN_BS      = 1
GRAD_ACCUM    = 16
EVAL_BS       = 1
PACKING       = True
LOG_STEPS     = 10
EVAL_STEPS    = 50
SAVE_STEPS    = 100
SEED          = 42
MAX_LENGTH    = None  # 필요 시 4096 등

USE_LORA      = True
LORA_R        = 16
LORA_ALPHA    = 32
LORA_DROPOUT  = 0.05
LORA_TARGETS  = "q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj"


MODEL_ID    = "microsoft/Phi-3.5-mini-instruct"

TRAIN_JSONL = "./input.jsonl"

EVAL_JSONL  = ""
OUTPUT_DIR  = f"./out/{MODEL_ID.split('/')[-1]}_with"

DEVICE_MAP    = "auto"
USE_BF16      = torch.cuda.is_available() and DEVICE_MAP != "cpu"


if HF_TOKEN:
    try:
        from huggingface_hub import login as hf_login
        hf_login(token=HF_TOKEN.strip())
        print("✅ HF 로그인 완료")
    except Exception as e:
        print(f"⚠️ HF 로그인 실패(무시): {e}")


def load_and_prepare_jsonl(train_path: str, eval_path: Optional[str], text_field: str = "text"):
    if not os.path.exists(train_path):
        raise FileNotFoundError(f"학습 파일 없음: {train_path}")

    data_files = {"train": train_path}
    if eval_path:
        if not os.path.exists(eval_path):
            raise FileNotFoundError(f"평가 파일 없음: {eval_path}")
        data_files["validation"] = eval_path

    ds = load_dataset("json", data_files=data_files)
    tr = ds["train"]; ev = ds.get("validation")

    cols = set(tr.column_names)

    if not ({"instruction", "output"}.issubset(cols) or {"input", "output"}.issubset(cols)):
        raise ValueError(
            "데이터 컬럼이 맞지 않습니다. 허용 스키마: "
            "[instruction, output] (+input 가능) 또는 [input, output]. "
            f"실제 컬럼: {tr.column_names}"
        )

    def to_text(ex):
        # 원본 필드 읽기
        instr = (ex.get("instruction") or "").strip()
        inp   = (ex.get("input") or "").strip()
        out   = (ex.get("output") or "").strip()

        if not instr and inp:
            instr, inp = inp, ""

        if not instr or not out:
            return None

        if inp:
            prompt = f"### Instruction:\n{instr}\n\n### Input:\n{inp}\n\n### Response:\n{out}"
        else:
            prompt = f"### Instruction:\n{instr}\n\n### Response:\n{out}"
        return {text_field: prompt}

    tr = tr.map(to_text, remove_columns=[], desc="format train").filter(lambda x: x.get(text_field) is not None)
    if ev is not None:
        ev = ev.map(to_text, remove_columns=[], desc="format eval").filter(lambda x: x.get(text_field) is not None)

    keep_cols = [text_field]
    tr = tr.remove_columns([c for c in tr.column_names if c not in keep_cols])
    if ev is not None:
        ev = ev.remove_columns([c for c in ev.column_names if c not in keep_cols])

    return tr, ev


def main():
    try:
        from huggingface_hub import HfApi
        HfApi().model_info(MODEL_ID, token=HF_TOKEN)
    except Exception as e:
        raise RuntimeError(
            f"모델 리포 확인 실패: {MODEL_ID}\n"
            f"→ 모델 ID/접근 권한(토큰·라이선스 동의) 점검 필요.\n원인: {e}"
        )

    try:
        import random, numpy as np
        random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(SEED)
    except Exception:
        pass

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("\n==== RUN ====")
    print(f"Model:       {MODEL_ID}")
    print(f"Train JSONL: {TRAIN_JSONL}")
    print(f"Eval JSONL:  {EVAL_JSONL or '(없음)'}")
    print(f"Output Dir:  {OUTPUT_DIR}")
    print(f"Epochs:      {EPOCHS} | LoRA r: {LORA_R if USE_LORA else '(off)'}")
    print("============\n")

    # 1) 토크나이저
    tok = AutoTokenizer.from_pretrained(
        MODEL_ID,
        use_fast=True,
        trust_remote_code=True,
        token=HF_TOKEN if HF_TOKEN else None
    )
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    # 2) 모델
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        device_map=DEVICE_MAP,
        dtype=torch.bfloat16 if USE_BF16 else torch.float32,
        trust_remote_code=True,
        token=HF_TOKEN if HF_TOKEN else None,
    )

    # gradient checkpointing
    try:
        model.gradient_checkpointing_enable()
    except Exception:
        pass

    # Flash Attention 2
    try:
        model.config.attn_implementation = "flash_attention_2"
    except Exception:
        pass
    print("✅ 모델/토크나이저 로드 완료")

    # 3) 데이터
    train_ds, eval_ds = load_and_prepare_jsonl(TRAIN_JSONL, EVAL_JSONL or None, "text")
    print("✅ 데이터 준비 완료")

    # 4) SFT 설정
    cfg = dict(
        output_dir=OUTPUT_DIR,
        dataset_text_field="text",
        packing=PACKING,
        per_device_train_batch_size=TRAIN_BS,
        per_device_eval_batch_size=EVAL_BS,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LR,
        num_train_epochs=EPOCHS,
        logging_steps=LOG_STEPS,
        eval_strategy="steps" if eval_ds is not None else "no",
        eval_steps=EVAL_STEPS if eval_ds is not None else None,
        save_strategy="steps",
        save_steps=SAVE_STEPS,
        seed=SEED,
        bf16=USE_BF16,
        report_to=[],
        gradient_checkpointing=True,
        # max_seq_length=4096,
    )
    if MAX_LENGTH is not None:
        cfg["max_length"] = MAX_LENGTH
    sft_config = SFTConfig(**cfg)

    # 5) LoRA 설정
    peft_cfg = None
    if USE_LORA:
        from peft import LoraConfig, TaskType
        targets = [t.strip() for t in LORA_TARGETS.split(",") if t.strip()]
        peft_cfg = LoraConfig(
            r=LORA_R, lora_alpha=LORA_ALPHA, lora_dropout=LORA_DROPOUT,
            bias="none", task_type=TaskType.CAUSAL_LM, target_modules=targets
        )
        print(f"✅ LoRA 적용(r={LORA_R}, alpha={LORA_ALPHA}, drop={LORA_DROPOUT})")

    # 6) 트레이너 & 학습
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=tok,
        peft_config=peft_cfg,
    )
    trainer.train()

    if eval_ds is not None:
        print("✅ 평가:", trainer.evaluate())

    # 7) 저장
    trainer.save_model(OUTPUT_DIR)
    tok.save_pretrained(OUTPUT_DIR)
    print(f"✅ 저장 완료 → {OUTPUT_DIR}")

    # 8) ZIP (선택)
    base = os.path.abspath(OUTPUT_DIR)
    shutil.make_archive(base, "zip", OUTPUT_DIR)
    print(f"✅ ZIP 생성 완료: {OUTPUT_DIR}.zip")

if __name__ == "__main__":
    main()