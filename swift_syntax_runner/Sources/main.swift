import SwiftSyntax
import SwiftParser
import Foundation

let inputPath = "../input.swift"
let outputGraphPath = "../output_graph.json"
let outputAstPath = "../output_ast.json"
let outputSwiftPath = "../output.swift"

func serializeSyntax(_ node: Syntax) -> [String: Any] {
    var result: [String: Any] = [:]
    result["type"] = String(describing: type(of: node))
    let trimmedText = node.trimmedDescription.trimmingCharacters(in: .whitespacesAndNewlines)
    if !trimmedText.isEmpty { result["text"] = trimmedText }
    let children = node.children(viewMode: .sourceAccurate).map { serializeSyntax($0) }
    if !children.isEmpty { result["children"] = children }
    return result
}

func extractCode(from node: [String: Any]) -> String {
    if let text = node["text"] as? String { return text + "\n" }
    var result = ""
    if let children = node["children"] as? [[String: Any]] {
        for child in children { result += extractCode(from: child) }
    }
    return result
}

func extractDependencyGraph(from node: [String: Any], parent: String? = nil) -> (Set<String>, Set<[String]>) {
    var nodes: Set<String> = []
    var edges: Set<[String]> = []

    func clean(_ text: String) -> String {
        return text
            .replacingOccurrences(of: "{", with: "")
            .replacingOccurrences(of: "}", with: "")
            .replacingOccurrences(of: "\n", with: "")
            .trimmingCharacters(in: .whitespaces)
    }

    func traverse(_ node: [String: Any], parent: String?) {
        var currentNodeName: String? = nil

        if let text = node["text"] as? String {
            let trimmed = clean(text)

            // 함수 정의
            if text.hasPrefix("func ") {
                let components = trimmed.split(separator: " ")
                if components.count >= 2 {
                    let funcName = String(components[1].split(separator: "(").first ?? "")
                    currentNodeName = funcName
                    nodes.insert(funcName)
                    if let p = parent, p != funcName {
                        edges.insert([p, funcName])
                    }
                }
            }

            // import 문
            else if text.hasPrefix("import ") {
                let module = trimmed.replacingOccurrences(of: "import", with: "").trimmingCharacters(in: .whitespaces)
                nodes.insert(module)
                edges.insert(["<current_file>", module])
            }

            // 클래스 상속
            else if text.contains("class") && text.contains(":") {
                let parts = trimmed.split(separator: ":").map { $0.trimmingCharacters(in: .whitespaces) }
                if parts.count == 2 {
                    let subclass = parts[0].replacingOccurrences(of: "class", with: "").trimmingCharacters(in: .whitespaces)
                    let superclass = parts[1].components(separatedBy: "{").first?.trimmingCharacters(in: .whitespaces) ?? ""
                    nodes.insert(subclass)
                    nodes.insert(superclass)
                    edges.insert([subclass, superclass])
                }
            }

            // 함수 호출
            else if text.contains("(") && !text.contains("func") && !text.contains("class") {
                let callTarget = text.components(separatedBy: "(").first?.trimmingCharacters(in: .whitespaces) ?? ""
                let callName = clean(callTarget)
                if !callName.isEmpty {
                    nodes.insert(callName)
                    if let p = parent, p != callName {
                        edges.insert([p, callName])
                    }
                }
            }
        }

        if let children = node["children"] as? [[String: Any]] {
            for child in children {
                traverse(child, parent: currentNodeName ?? parent)
            }
        }
    }

    traverse(node, parent: nil)
    return (nodes, edges)
}



// ====== 🟢 MAIN 실행 영역 ======
let sourceCode = try String(contentsOfFile: inputPath)
let tree = Parser.parse(source: sourceCode)
let jsonTree = serializeSyntax(Syntax(tree))

let jsonData = try JSONSerialization.data(withJSONObject: jsonTree, options: [.prettyPrinted])
try jsonData.write(to: URL(fileURLWithPath: outputAstPath))
print("✅ AST JSON 저장 완료: \(outputAstPath)")

guard let jsonRoot = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any] else {
    print("❌ JSON 파싱 오류")
    exit(1)
}

let restoredCode = extractCode(from: jsonRoot)
try restoredCode.write(toFile: outputSwiftPath, atomically: true, encoding: .utf8)
print("✅ Swift 코드 복원 완료: \(outputSwiftPath)")

let (nodes, edges) = extractDependencyGraph(from: jsonRoot)
let graphJson: [String: Any] = [
    "nodes": Array(nodes),
    "edges": Array(edges)
]
let graphData = try JSONSerialization.data(withJSONObject: graphJson, options: [.prettyPrinted])
try graphData.write(to: URL(fileURLWithPath: outputGraphPath))
print("✅ 의존 그래프 저장 완료: \(outputGraphPath)")
