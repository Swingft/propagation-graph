import os
import json
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import List, Dict, Any, Optional
from tqdm import tqdm


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
ANALYZER_DIR = PROJECT_ROOT / "SwiftASTAnalyzer"
TARGET_DATA_ROOT = PROJECT_ROOT / "data"
OUTPUT_ROOT = PROJECT_ROOT / "llm_training_inputs"

# --- LLM 프롬프트 구조화 ---
# [CoT 개선] LLM의 역할을 정의하고, Chain-of-Thought 응답을 생성해야 함을 명시.
LLM_INSTRUCTION = """Your Role: You are an expert static analysis assistant with a deep understanding of Swift's semantic structure. Your mission is to meticulously analyze the provided symbol information to identify which symbols must have their names preserved during code obfuscation.

**CRITICAL**: You MUST follow a strict Chain-of-Thought process. First, provide your step-by-step reasoning within a `<thinking>` block. After your reasoning is complete, provide the final JSON object.
"""

# [CoT]
LLM_TASK_GUIDELINES = {
    "procedure": [
        "1. Start your entire response with a `<thinking>` block.",
        "2. Inside the `<thinking>` block, analyze EACH symbol from the `symbol_data_for_analysis` one by one.",
        "3. For each symbol, use the `mapping_context` to decode the abbreviated keys (e.g., 'p3' means 'access_level').",
        "4. State your decision for each symbol (exclude or not) and justify it by referencing the 'Core Analysis Patterns'.",
        "5. After analyzing all symbols and closing the `</thinking>` tag, provide the final, clean JSON object containing only the symbols that must be excluded."
    ],
    "core_analysis_patterns": {
        "Runtime String References (`objc_selector`, `stringly_typed_api`)": "A symbol's name must be preserved if it is referenced as a raw string at runtime. This includes Objective-C selectors (#selector) which rely on the Objective-C runtime to find methods by their string name, and other stringly-typed APIs like Notification.Name or UserDefaults keys. Obfuscating the symbol's name would break this lookup mechanism, leading to runtime crashes.",
        "KVC/KVO and Data Binding (`kvc_kvo`, `coredata_nsmanaged`)": "Preservation is required when a symbol is accessed through dynamic, string-based mechanisms like Key-Value Coding (KVC), Key-Value Observing (KVO), or KeyPath. Similarly, CoreData's @NSManaged properties dynamically generate accessors at runtime based on the property name matching the nC1 model. Changing these names will cause runtime exceptions as the lookup mechanism will fail.",
        "C Function Interface (FFI) Exposure (`ffi_entry`)": "A symbol exposed to C/C++/Objective-C via attributes like `@_cdecl` must retain its name. This attribute creates a symbol in the binary with the exact function name, forming a contract with external code. Obfuscating it would result in linking errors or an inability for external code to find and call the function.",
        "Reflection (`runtime_reflection`)": "Symbols whose names are accessed via runtime reflection, such as through Swift's `Mirror` API, must not be changed. Reflection-based logic (e.g., for serialization, debugging, or dynamic UI generation) often inspects property names as strings (`child.label`). Obfuscation would make this introspection yield incorrect nC1, breaking the feature.",
        "Codable Synthesis (`codable_synthesized`)": "When the compiler automatically synthesizes `Codable` conformance, property names are used directly as keys in the serialized format (e.g., JSON). Obfuscating these property names would change the keys in the output, breaking API contracts with servers or preventing previously stored nC1 from being decoded correctly.",
        "Resource Binding (`resource_binding`)": "A symbol's name must be preserved if it is used to link to external resources. This includes names used in `UIImage(named:)`, Storyboard IDs, XIB file connections, or asset catalog names. Obfuscating these string-based identifiers breaks the connection between code and resources, preventing them from being loaded.",
        "External Contracts and Extensions (`external_contract`)": "Any `public` or `open` symbol is part of a module's public API, which forms a stable contract (ABI) with other modules. If a symbol's name in this API is changed, any external code that depends on it will fail to compile or will crash at runtime due to missing symbols. Its name is a non-negotiable part of the contract.",
        "Dynamic Dispatch & ObjC Exposure (`dynamic_dispatch`, `objc_exposed`)": "Symbols marked with `@objc` and/or `dynamic` must have their names preserved. These keywords ensure the symbol is available to the Objective-C runtime and that method calls are dispatched dynamically. The runtime relies on the symbol's name for message passing; obfuscating it would make the symbol undiscoverable.",
        "Protocol Requirement Implementation (`protocol_requirement`)": "A symbol that fulfills a protocol requirement must maintain its original name. The Swift compiler and runtime verify protocol conformance by matching the exact names and type signatures of the required members. If an implementation's name is obfuscated, the type will no longer correctly conform to the protocol, leading to compile-time errors or runtime crashes."
    },
    "output_format": {
        "description": "Your response MUST consist of two parts: a reasoning block followed by a JSON block.",
        "reasoning_block": "A `<thinking>...</thinking>` block containing your step-by-step analysis of each symbol.",
        "json_block_format": {
            "description": "A valid JSON object containing ONLY the symbols that must be excluded from obfuscation.",
            "fields": {
                "symbol_name": "The pure name excluding function arguments.",
                "tags": "An array of standard tags corresponding to the reason for exclusion.",
                "rationale": "A clear, 1-2 sentence explanation for the exclusion, based on the input nC1."
            }
        }
    }
}

KEY_MAPPING = {
    "is_protocol_requirement_impl": "p1", "codable_synthesized": "p2", "access_level": "p3",
    "is_ffi_entry": "p4", "override_depth": "p5", "modifiers": "p6", "is_coredata_nsmanaged": "p7",
    "ast_path": "p8", "cross_module_refs": "p9", "is_objc_exposed": "p10", "type_signature": "p11",
    "extension_file_count_same_name": "p12", "is_swiftdata_model": "p13", "symbol_kind": "p14",
    "references": "p15", "calls_out": "p16", "selector_refs": "p17", "attributes": "p18",
    "extension_of": "p19", "inherits": "p20", "conforms": "p21"
}


def build_analyzer(analyzer_dir: Path) -> Path:
    """SwiftASTAnalyzer를 릴리즈 모드로 빌드하고 실행 파일 경로를 반환합니다."""
    print("🚀 SwiftASTAnalyzer 빌드를 시작합니다...")
    analyzer_bin_name = "swift-ast-analyzer"
    try:
        subprocess.run(
            ["swift", "build", "-c", "release"],
            cwd=analyzer_dir, check=True, capture_output=True, text=True,
        )
        print("✅ 빌드 완료!")
        analyzer_bin = analyzer_dir / ".build" / "release" / analyzer_bin_name
        if not analyzer_bin.exists():
            raise FileNotFoundError(f"빌드 후에도 실행 파일을 찾을 수 없습니다: {analyzer_bin}")
        return analyzer_bin
    except subprocess.CalledProcessError as e:
        print(f"🔥 빌드 실패! 컴파일러 오류:\n{e.stderr}")
        raise


def find_swift_files(root: Path) -> List[Path]:
    """지정된 루트 디렉토리 아래의 모든 .swift 파일을 재귀적으로 검색합니다."""
    print(f"🔎 '{root}' 디렉토리에서 Swift 파일들을 검색합니다...")
    swift_files = list(root.rglob("*.swift"))
    print(f"✨ 총 {len(swift_files)}개의 Swift 파일을 찾았습니다.")
    return swift_files

def _clean_and_compact_decisions(decisions_data: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    """분석 결과('decisions') 데이터에 대해 키 간결화 및 정제 작업을 수행합니다."""
    if not isinstance(decisions_data, dict):
        return decisions_data

    for category, symbols in decisions_data.items():
        if isinstance(symbols, list):
            for symbol_obj in symbols:
                if 'input' in symbol_obj and isinstance(symbol_obj['input'], dict):
                    original_input = symbol_obj['input']
                    compacted_input = {
                        mapping.get(key, key): value
                        for key, value in original_input.items()
                        if not (isinstance(value, list) and not value)
                    }
                    symbol_obj['input'] = compacted_input

    cleaned_decisions = {
        category: symbols for category, symbols in decisions_data.items()
        if isinstance(symbols, list) and symbols
    }
    return cleaned_decisions

def _create_llm_input_object(guidelines: Dict[str, Any], mapping: Dict[str, str], decisions: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM의 'input' 필드에 들어갈 구조화된 딕셔너리를 생성합니다.
    """
    return {
        "guidelines": guidelines,
        "mapping_context": mapping,
        "symbol_data_for_analysis": decisions
    }

def analyze_single_file(
    swift_file: Path, analyzer_bin: Path, data_root: Path, output_root: Path
) -> Optional[str]:
    """단일 Swift 파일을 분석하고, LLM 학습에 적합한 JSON 형식으로 변환하여 저장합니다."""
    try:
        relative_path = swift_file.relative_to(data_root)
        output_dir = output_root / relative_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"training_input_{swift_file.stem}.json"

        result = subprocess.run(
            [str(analyzer_bin), str(swift_file)],
            capture_output=True, text=True, check=True, encoding="utf-8",
        )
        original_data = json.loads(result.stdout)

        decisions_data = original_data.get('decisions', {})
        cleaned_decisions = _clean_and_compact_decisions(decisions_data, KEY_MAPPING)

        if not cleaned_decisions:
            return f"ℹ️ {swift_file} 파일에서 유의미한 심볼을 찾지 못해 건너뜁니다."

        llm_input_object = _create_llm_input_object(LLM_TASK_GUIDELINES, KEY_MAPPING, cleaned_decisions)

        final_training_data = {
            "instruction": LLM_INSTRUCTION.strip(),
            "input": llm_input_object,
            "output": ""
        }

        output_file.write_text(json.dumps(final_training_data, indent=2, ensure_ascii=False), encoding="utf-8")

        return None

    except json.JSONDecodeError:
        return f"❌ {swift_file} 분석 실패: Swift 분석기가 유효한 JSON을 생성하지 않았습니다."
    except subprocess.CalledProcessError as e:
        return f"❌ {swift_file} 분석 실패 (Subprocess Error):\n{e.stderr}"
    except Exception as e:
        return f"❌ {swift_file} 처리 중 예외 발생:\n{e}"


def main():
    """스크립트의 메인 실행 함수"""
    try:
        analyzer_bin = build_analyzer(ANALYZER_DIR)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return

    swift_files = find_swift_files(TARGET_DATA_ROOT)
    if not swift_files:
        print("⚠️ 분석할 Swift 파일이 없습니다. 스크립트를 종료합니다.")
        return

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"\n⚙️ 총 {len(swift_files)}개 파일에 대한 병렬 분석을 시작합니다...")

    worker_func = partial(
        analyze_single_file,
        analyzer_bin=analyzer_bin,
        data_root=TARGET_DATA_ROOT,
        output_root=OUTPUT_ROOT,
    )

    success_count = 0
    errors = []
    infos = []
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        results = list(tqdm(
            executor.map(worker_func, swift_files),
            total=len(swift_files),
            desc="파일 분석 중"
        ))

    for res in results:
        if res is None:
            success_count += 1
        elif res.startswith("❌"):
            errors.append(res)
        elif res.startswith("ℹ️"):
            infos.append(res)

    print("\n--- 분석 완료 ---")
    if infos:
        print(f"🔹 정보 ({len(infos)}건):")
        for info_log in infos:
            print(f"   {info_log}")

    if errors:
        print(f"🔥 오류 ({len(errors)}건):")
        for error_log in errors:
            print(f"   {error_log}")

    print(f"\n🎉 {success_count}개의 파일이 성공적으로 처리되어 학습 입력 데이터로 변환되었습니다!")
    if errors:
        print(f"   (오류가 발생한 {len(errors)}개 파일은 제외되었습니다.)")


if __name__ == "__main__":
    main()

