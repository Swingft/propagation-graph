#!/bin/bash

echo "▶️ SwiftSyntax 실행 중..."
cd swift_syntax_runner
swift build
.build/debug/swift_syntax_runner
cd ..
echo "▶️ 의존 그래프 시각화 실행 중..."
python visualize_graph.py