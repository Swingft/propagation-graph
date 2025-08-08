#!/bin/bash
set -e

echo "▶️ SwiftSyntax 실행 중..."

cd SwiftASTAnalyzer
swift build -c release

# ./input.swift 분석 후 JSON 저장
.build/release/swift-ast-analyzer ./input.swift > ./output.json

echo "✅ 분석 완료: output.json 생성됨"
