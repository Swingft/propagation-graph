import Foundation
import SwiftSyntax
import SwiftParser

// MARK: - Models

struct SymbolInput: Codable {
    var symbol_kind: String
    var ast_path: [String]
    var access_level: String
    var modifiers: [String]
    var attributes: [String]
    var type_signature: String
    var inherits: [String]
    var conforms: [String]
    var is_protocol_requirement_impl: Bool
    var override_depth: Int
    var extension_of: String?
    var extension_file_count_same_name: Int
    var calls_out: [String]
    var called_by: [String]
    var references: [String]
    var keypath_refs: [String]
    var selector_refs: [String]
    var kvc_kvo_strings: [String]
    var ffi_names: [String]
    var is_coredata_nsmanaged: Bool
    var is_swiftdata_model: Bool
    var codable_synthesized: Bool
    var is_ffi_entry: Bool
    var is_objc_exposed: Bool
    var cross_module_refs: Bool
}

struct Decision: Codable {
    var exclude: String // "yes" | "no" | "unsure"
    var tags: [String]
    var rationale: String
}

struct SymbolRecord: Codable {
    var symbol_id: String
    var symbol_name: String
    var input: SymbolInput
    var decision: Decision?
}

struct Decisions: Codable {
    var classes: [SymbolRecord] = []
    var structs: [SymbolRecord] = []
    var enums: [SymbolRecord] = []
    var protocols: [SymbolRecord] = []
    var extensions: [SymbolRecord] = []
    var methods: [SymbolRecord] = []
    var properties: [SymbolRecord] = []
    var variables: [SymbolRecord] = []
    var enumCases: [SymbolRecord] = []
    var initializers: [SymbolRecord] = []
    var deinitializers: [SymbolRecord] = []
    var subscripts: [SymbolRecord] = []
}

struct Meta: Codable {
    var tool: String
    var model: String
    var prompt_context: String
}

struct OutputJSON: Codable {
    var meta: Meta
    var decisions: Decisions
}

// MARK: - Utilities

func accessLevel(from modifiers: DeclModifierListSyntax?) -> String {
    guard let mods = modifiers else { return "internal" }
    for m in mods {
        let name = m.name.text.lowercased()
        if ["public", "open", "internal", "fileprivate", "private"].contains(name) {
            return name
        }
    }
    return "internal"
}

func collectModifiers(_ modifiers: DeclModifierListSyntax?) -> [String] {
    guard let mods = modifiers else { return [] }
    return mods.map { $0.name.text }
}

func collectAttributes(_ attrs: AttributeListSyntax?) -> [String] {
    guard let attrs = attrs else { return [] }
    return attrs.compactMap { attr in
        if let a = attr.as(AttributeSyntax.self) {
            return "@\(a.attributeName.trimmedDescription)"
        }
        return nil
    }
}

func inheritsFrom(_ clause: InheritanceClauseSyntax?) -> [String] {
    guard let clause = clause else { return [] }
    return clause.inheritedTypes.map { $0.type.trimmedDescription }
}

func funcTypeSignature(_ decl: FunctionDeclSyntax) -> String {
    decl.signature.trimmedDescription
}

func varTypeSignature(_ decl: VariableDeclSyntax) -> String {
    if let binding = decl.bindings.first, let typeAnno = binding.typeAnnotation {
        return typeAnno.type.trimmedDescription
    }
    return ""
}

func propertyNames(_ decl: VariableDeclSyntax) -> [String] {
    decl.bindings.compactMap {
        $0.pattern.as(IdentifierPatternSyntax.self)?.identifier.text
    }
}

func functionName(_ decl: FunctionDeclSyntax) -> String { decl.name.text }

func initializerSignature(_ decl: InitializerDeclSyntax) -> String {
    decl.signature.trimmedDescription
}

func deinitializerSignature(_ decl: DeinitializerDeclSyntax) -> String { "deinit" }

func subscriptSignature(_ decl: SubscriptDeclSyntax) -> String {
    decl.parameterClause.parameters.trimmedDescription
}

func qualTypeName(stack: [String], currentType: String?) -> String {
    (stack + [currentType].compactMap { $0 }).joined(separator: ".")
}

// MARK: - Body scan visitor (최상위 클래스)

final class BodyVisitor: SyntaxVisitor {
    var calls: [String] = []
    var keypaths: [String] = []
    var selectors: [String] = []
    var kvc: [String] = []
    var refs: [String] = []

    override func visit(_ node: FunctionCallExprSyntax) -> SyntaxVisitorContinueKind {
        // 호출된 함수의 이름만 정확히 추출합니다. (예: `LazyVGrid`, `Text`)
        if let calledExpr = node.calledExpression.as(DeclReferenceExprSyntax.self) {
            calls.append(calledExpr.baseName.text)
        } else if let memberAccess = node.calledExpression.as(MemberAccessExprSyntax.self) {
            calls.append(memberAccess.declName.baseName.text)
        }

        // KVC 관련 로직은 기존대로 유지
        let nameText = (node.calledExpression.trimmedDescription).lowercased()
        let kvcLikely = nameText.contains("valueforkey")
            || nameText.contains("setvalue")
            || nameText.contains("addobserver")
            || nameText.contains("removeobserver")
        if kvcLikely {
            for arg in node.arguments {
                if let s = arg.expression.as(StringLiteralExprSyntax.self) {
                    kvc.append(s.trimmedDescription)
                }
            }
        }
        return .visitChildren
    }

    override func visit(_ node: KeyPathExprSyntax) -> SyntaxVisitorContinueKind {
        keypaths.append(node.trimmedDescription)
        return .visitChildren
    }

    override func visit(_ node: DeclReferenceExprSyntax) -> SyntaxVisitorContinueKind {
        // 참조된 심볼의 기본 이름만 추가합니다.
        refs.append(node.baseName.text)
        return .visitChildren
    }

    override func visit(_ node: MemberAccessExprSyntax) -> SyntaxVisitorContinueKind {
        // 멤버 접근 시, 멤버의 이름만 추가합니다. (예: `.padding`, `.onTapGesture`)
        refs.append(node.declName.baseName.text)
        return .visitChildren
    }
}

private func scanBodySignals(_ syntax: Syntax) -> (calls:[String], keypaths:[String], selectors:[String], kvc:[String], refs:[String]) {
    let v = BodyVisitor(viewMode: .sourceAccurate)
    v.walk(syntax)

    // 텍스트 기반 selector 추출
    var selectorTexts: [String] = []
    let text = syntax.trimmedDescription
    if let regex = try? NSRegularExpression(pattern: #"#selector\s*\([^)]+\)"#) {
        let ns = text as NSString
        let matches = regex.matches(in: text, range: NSRange(location: 0, length: ns.length))
        for m in matches {
            selectorTexts.append(ns.substring(with: m.range))
        }
    }

    func uniq(_ a:[String]) -> [String] { Array(Set(a)).sorted() }
    return (uniq(v.calls), uniq(v.keypaths), uniq(selectorTexts), uniq(v.kvc), uniq(v.refs))
}

// MARK: - Project-wide bookkeeping

final class ProjectContext {
    var extensionCount: [String: Int] = [:]
    func bumpExtension(_ typeName: String) {
        extensionCount[typeName, default: 0] += 1
    }
    func count(for typeName: String) -> Int {
        extensionCount[typeName, default: 0]
    }
}

func prepassCountExtensions(filePaths: [String]) -> ProjectContext {
    let ctx = ProjectContext()
    for path in filePaths {
        guard let source = try? String(contentsOfFile: path, encoding: .utf8) else { continue }
        let tree = Parser.parse(source: source)
        let visitor = ExtensionCounter(ctx: ctx)
        visitor.walk(tree)
    }
    return ctx
}

final class ExtensionCounter: SyntaxVisitor {
    let ctx: ProjectContext
    init(ctx: ProjectContext) {
        self.ctx = ctx
        super.init(viewMode: .sourceAccurate)
    }
    override func visit(_ node: ExtensionDeclSyntax) -> SyntaxVisitorContinueKind {
        let name = node.extendedType.trimmedDescription
        ctx.bumpExtension(name)
        return .visitChildren
    }
}

// MARK: - Main Visitor

final class SymbolCollector: SyntaxVisitor {
    private let filePath: String
    private let source: String
    private let converter: SourceLocationConverter
    private let projectCtx: ProjectContext

    private var typeStack: [String] = []
    var decisions = Decisions()

    init(filePath: String, source: String, projectCtx: ProjectContext) {
        self.filePath = filePath
        self.source = source
        let parsed = Parser.parse(source: source)
        self.converter = SourceLocationConverter(fileName: filePath, tree: parsed)
        self.projectCtx = projectCtx
        super.init(viewMode: .sourceAccurate)
    }

    private func symbolID(of node: some SyntaxProtocol) -> String {
        let start = node.positionAfterSkippingLeadingTrivia
        let loc = converter.location(for: start)
        return "\(filePath):\(loc.line):\(loc.column)"
    }

    private func baseAttributesFlags(_ attrs: [String], modifiers: [String]) -> (isObjcExposed: Bool, isCoreData: Bool, isSwiftData: Bool, isFfi: Bool, ffiNames: [String]) {
        let set = Set(attrs.map { $0.lowercased() })
        let dyn = modifiers.map { $0.lowercased() }.contains("dynamic")
        let isObjc = set.contains("@objc") || set.contains("@objcmembers") || dyn
        let isCoreData = set.contains("@nsmanaged")
        let isSwiftData = set.contains("@model")
        let ffi = set.contains("@_cdecl") || set.contains("@_silgen_name")

        var ffiNames: [String] = []
        for a in attrs {
            if a.lowercased().starts(with: "@_cdecl"), let open = a.firstIndex(of: "("), let close = a.lastIndex(of: ")") {
                let inner = a[a.index(after: open)..<close]
                ffiNames.append(String(inner))
            }
            if a.lowercased().starts(with: "@_silgen_name"), let open = a.firstIndex(of: "("), let close = a.lastIndex(of: ")") {
                let inner = a[a.index(after: open)..<close]
                ffiNames.append(String(inner))
            }
        }
        return (isObjc, isCoreData, isSwiftData, ffi, ffiNames)
    }

    // MARK: - Type Decls

    override func visit(_ node: ClassDeclSyntax) -> SyntaxVisitorContinueKind {
        typeStack.append(node.name.text)
        defer { _ = typeStack.popLast() }

        let modifiers = collectModifiers(node.modifiers)
        let attrs = collectAttributes(node.attributes)
        let (isObjc, isCoreData, isSwiftData, isFfi, ffiNames) = baseAttributesFlags(attrs, modifiers: modifiers)

        let access = accessLevel(from: node.modifiers)
        let inherits = inheritsFrom(node.inheritanceClause)
        let conforms: [String] = inherits

        let codableLike = conforms.contains(where: { ["Decodable","Encodable","Codable"].contains($0) })
        var hasCodingKeys = false
        for member in node.memberBlock.members {
            if let enumDecl = member.decl.as(EnumDeclSyntax.self), enumDecl.name.text == "CodingKeys" {
                hasCodingKeys = true
                break
            }
        }

        let symbolID = symbolID(of: node)
        let qualName = qualTypeName(stack: typeStack.dropLast().map{$0}, currentType: node.name.text)

        let input = SymbolInput(
            symbol_kind: "class",
            ast_path: ["SourceFile", "ClassDecl"],
            access_level: access,
            modifiers: modifiers,
            attributes: attrs,
            type_signature: "",
            inherits: inherits,
            conforms: conforms,
            is_protocol_requirement_impl: false,
            override_depth: 0,
            extension_of: nil,
            extension_file_count_same_name: projectCtx.count(for: qualName),
            calls_out: [],
            called_by: [],
            references: [],
            keypath_refs: [],
            selector_refs: [],
            kvc_kvo_strings: [],
            ffi_names: ffiNames,
            is_coredata_nsmanaged: isCoreData,
            is_swiftdata_model: isSwiftData,
            codable_synthesized: codableLike && !hasCodingKeys,
            is_ffi_entry: isFfi,
            is_objc_exposed: isObjc,
            cross_module_refs: false
        )

        let rec = SymbolRecord(symbol_id: symbolID, symbol_name: qualName, input: input, decision: nil)
        decisions.classes.append(rec)
        return .visitChildren
    }

    override func visit(_ node: StructDeclSyntax) -> SyntaxVisitorContinueKind {
        typeStack.append(node.name.text)
        defer { _ = typeStack.popLast() }

        let modifiers = collectModifiers(node.modifiers)
        let attrs = collectAttributes(node.attributes)
        let (isObjc, isCoreData, isSwiftData, isFfi, ffiNames) = baseAttributesFlags(attrs, modifiers: modifiers)
        let access = accessLevel(from: node.modifiers)
        let conforms = inheritsFrom(node.inheritanceClause)

        let codableLike = conforms.contains(where: { ["Decodable","Encodable","Codable"].contains($0) })
        var hasCodingKeys = false
        for member in node.memberBlock.members {
            if let enumDecl = member.decl.as(EnumDeclSyntax.self), enumDecl.name.text == "CodingKeys" {
                hasCodingKeys = true
                break
            }
        }

        let qualName = qualTypeName(stack: typeStack.dropLast().map{$0}, currentType: node.name.text)
        let symbolID = symbolID(of: node)

        let input = SymbolInput(
            symbol_kind: "struct",
            ast_path: ["SourceFile", "StructDecl"],
            access_level: access,
            modifiers: modifiers,
            attributes: attrs,
            type_signature: "",
            inherits: [],
            conforms: conforms,
            is_protocol_requirement_impl: false,
            override_depth: 0,
            extension_of: nil,
            extension_file_count_same_name: projectCtx.count(for: qualName),
            calls_out: [],
            called_by: [],
            references: [],
            keypath_refs: [],
            selector_refs: [],
            kvc_kvo_strings: [],
            ffi_names: ffiNames,
            is_coredata_nsmanaged: isCoreData,
            is_swiftdata_model: isSwiftData,
            codable_synthesized: codableLike && !hasCodingKeys,
            is_ffi_entry: isFfi,
            is_objc_exposed: isObjc,
            cross_module_refs: false
        )
        let rec = SymbolRecord(symbol_id: symbolID, symbol_name: qualName, input: input, decision: nil)
        decisions.structs.append(rec)
        return .visitChildren
    }

    override func visit(_ node: EnumDeclSyntax) -> SyntaxVisitorContinueKind {
        typeStack.append(node.name.text)
        defer { _ = typeStack.popLast() }

        let modifiers = collectModifiers(node.modifiers)
        let attrs = collectAttributes(node.attributes)
        let (isObjc, isCoreData, isSwiftData, isFfi, ffiNames) = baseAttributesFlags(attrs, modifiers: modifiers)
        let access = accessLevel(from: node.modifiers)
        let conforms = inheritsFrom(node.inheritanceClause)

        let qualName = qualTypeName(stack: typeStack.dropLast().map{$0}, currentType: node.name.text)
        let symbolID = symbolID(of: node)

        let input = SymbolInput(
            symbol_kind: "enum",
            ast_path: ["SourceFile", "EnumDecl"],
            access_level: access,
            modifiers: modifiers,
            attributes: attrs,
            type_signature: "",
            inherits: [],
            conforms: conforms,
            is_protocol_requirement_impl: false,
            override_depth: 0,
            extension_of: nil,
            extension_file_count_same_name: projectCtx.count(for: qualName),
            calls_out: [],
            called_by: [],
            references: [],
            keypath_refs: [],
            selector_refs: [],
            kvc_kvo_strings: [],
            ffi_names: ffiNames,
            is_coredata_nsmanaged: isCoreData,
            is_swiftdata_model: isSwiftData,
            codable_synthesized: false,
            is_ffi_entry: isFfi,
            is_objc_exposed: isObjc,
            cross_module_refs: false
        )
        let rec = SymbolRecord(symbol_id: symbolID, symbol_name: qualName, input: input, decision: nil)
        decisions.enums.append(rec)
        return .visitChildren
    }

    override func visit(_ node: ProtocolDeclSyntax) -> SyntaxVisitorContinueKind {
        typeStack.append(node.name.text)
        defer { _ = typeStack.popLast() }

        let modifiers = collectModifiers(node.modifiers)
        let attrs = collectAttributes(node.attributes)
        let (isObjc, isCoreData, isSwiftData, isFfi, ffiNames) = baseAttributesFlags(attrs, modifiers: modifiers)
        let access = accessLevel(from: node.modifiers)

        let qualName = qualTypeName(stack: typeStack.dropLast().map{$0}, currentType: node.name.text)
        let symbolID = symbolID(of: node)

        let input = SymbolInput(
            symbol_kind: "protocol",
            ast_path: ["SourceFile", "ProtocolDecl"],
            access_level: access,
            modifiers: modifiers,
            attributes: attrs,
            type_signature: "",
            inherits: [],
            conforms: [],
            is_protocol_requirement_impl: false,
            override_depth: 0,
            extension_of: nil,
            extension_file_count_same_name: projectCtx.count(for: qualName),
            calls_out: [],
            called_by: [],
            references: [],
            keypath_refs: [],
            selector_refs: [],
            kvc_kvo_strings: [],
            ffi_names: ffiNames,
            is_coredata_nsmanaged: isCoreData,
            is_swiftdata_model: isSwiftData,
            codable_synthesized: false,
            is_ffi_entry: isFfi,
            is_objc_exposed: isObjc,
            cross_module_refs: false
        )
        let rec = SymbolRecord(symbol_id: symbolID, symbol_name: qualName, input: input, decision: nil)
        decisions.protocols.append(rec)
        return .visitChildren
    }

    override func visit(_ node: ExtensionDeclSyntax) -> SyntaxVisitorContinueKind {
        let typeName = node.extendedType.trimmedDescription
        typeStack.append(typeName)
        defer { _ = typeStack.popLast() }

        let modifiers = collectModifiers(node.modifiers)
        let attrs = collectAttributes(node.attributes)
        let (isObjc, isCoreData, isSwiftData, isFfi, ffiNames) = baseAttributesFlags(attrs, modifiers: modifiers)
        let access = accessLevel(from: node.modifiers)
        let conforms = inheritsFrom(node.inheritanceClause)
        let qualName = qualTypeName(stack: typeStack.dropLast().map{$0}, currentType: nil)
        let symbolID = symbolID(of: node)

        let input = SymbolInput(
            symbol_kind: "extension",
            ast_path: ["SourceFile","ExtensionDecl"],
            access_level: access,
            modifiers: modifiers,
            attributes: attrs,
            type_signature: "",
            inherits: [],
            conforms: conforms,
            is_protocol_requirement_impl: false,
            override_depth: 0,
            extension_of: typeName,
            extension_file_count_same_name: projectCtx.count(for: typeName),
            calls_out: [],
            called_by: [],
            references: [],
            keypath_refs: [],
            selector_refs: [],
            kvc_kvo_strings: [],
            ffi_names: ffiNames,
            is_coredata_nsmanaged: isCoreData,
            is_swiftdata_model: isSwiftData,
            codable_synthesized: false,
            is_ffi_entry: isFfi,
            is_objc_exposed: isObjc,
            cross_module_refs: false
        )
        let rec = SymbolRecord(symbol_id: symbolID, symbol_name: qualName, input: input, decision: nil)
        decisions.extensions.append(rec)
        return .visitChildren
    }

    // MARK: - Members

    override func visit(_ node: FunctionDeclSyntax) -> SyntaxVisitorContinueKind {
        let modifiers = collectModifiers(node.modifiers)
        let attrs = collectAttributes(node.attributes)
        let (isObjc, isCoreData, isSwiftData, isFfi, ffiNames) = baseAttributesFlags(attrs, modifiers: modifiers)
        let access = accessLevel(from: node.modifiers)

        let sig = funcTypeSignature(node)
        let name = functionName(node)
        let qualBase = qualTypeName(stack: typeStack, currentType: nil)
        let qualName = (qualBase.isEmpty ? "" : "\(qualBase).") + name
        let symbolID = symbolID(of: node)

        let bodySyntax: Syntax = node.body.map { Syntax($0) } ?? Syntax(node)
        let (calls, kps, sels, kvc, refs) = scanBodySignals(bodySyntax)

        let input = SymbolInput(
            symbol_kind: "method",
            ast_path: ["SourceFile"] + typeStack.map { "\($0)Decl" } + ["FuncDecl"],
            access_level: access,
            modifiers: modifiers,
            attributes: attrs,
            type_signature: sig,
            inherits: [],
            conforms: [],
            is_protocol_requirement_impl: false,
            override_depth: modifiers.map{$0.lowercased()}.contains("override") ? 1 : 0,
            extension_of: nil,
            extension_file_count_same_name: 0,
            calls_out: calls,
            called_by: [],
            references: refs,
            keypath_refs: kps,
            selector_refs: sels,
            kvc_kvo_strings: kvc,
            ffi_names: ffiNames,
            is_coredata_nsmanaged: isCoreData,
            is_swiftdata_model: isSwiftData,
            codable_synthesized: false,
            is_ffi_entry: isFfi,
            is_objc_exposed: isObjc,
            cross_module_refs: false
        )
        let rec = SymbolRecord(symbol_id: symbolID, symbol_name: "\(qualName)(\(sig))", input: input, decision: nil)
        decisions.methods.append(rec)
        return .visitChildren
    }

    override func visit(_ node: InitializerDeclSyntax) -> SyntaxVisitorContinueKind {
        let modifiers = collectModifiers(node.modifiers)
        let attrs = collectAttributes(node.attributes)
        let (isObjc, isCoreData, isSwiftData, isFfi, ffiNames) = baseAttributesFlags(attrs, modifiers: modifiers)
        let access = accessLevel(from: node.modifiers)
        let sig = initializerSignature(node)

        let qualName = qualTypeName(stack: typeStack, currentType: nil) + ".init"
        let symbolID = symbolID(of: node)

        let bodySyntax: Syntax = node.body.map { Syntax($0) } ?? Syntax(node)
        let (calls, kps, sels, kvc, refs) = scanBodySignals(bodySyntax)

        let input = SymbolInput(
            symbol_kind: "initializer",
            ast_path: ["SourceFile"] + typeStack.map { "\($0)Decl" } + ["InitializerDecl"],
            access_level: access,
            modifiers: modifiers,
            attributes: attrs,
            type_signature: sig,
            inherits: [],
            conforms: [],
            is_protocol_requirement_impl: false,
            override_depth: 0,
            extension_of: nil,
            extension_file_count_same_name: 0,
            calls_out: calls,
            called_by: [],
            references: refs,
            keypath_refs: kps,
            selector_refs: sels,
            kvc_kvo_strings: kvc,
            ffi_names: ffiNames,
            is_coredata_nsmanaged: isCoreData,
            is_swiftdata_model: isSwiftData,
            codable_synthesized: false,
            is_ffi_entry: isFfi,
            is_objc_exposed: isObjc,
            cross_module_refs: false
        )
        let rec = SymbolRecord(symbol_id: symbolID, symbol_name: "\(qualName)(\(sig))", input: input, decision: nil)
        decisions.initializers.append(rec)
        return .visitChildren
    }

    override func visit(_ node: DeinitializerDeclSyntax) -> SyntaxVisitorContinueKind {
        let modifiers = collectModifiers(node.modifiers)
        let attrs = collectAttributes(node.attributes)
        let (isObjc, isCoreData, isSwiftData, isFfi, ffiNames) = baseAttributesFlags(attrs, modifiers: modifiers)
        let access = accessLevel(from: node.modifiers)
        let sig = deinitializerSignature(node)

        let qualName = qualTypeName(stack: typeStack, currentType: nil) + ".deinit"
        let symbolID = symbolID(of: node)

        let bodySyntax: Syntax = node.body.map { Syntax($0) } ?? Syntax(node)
        let (calls, kps, sels, kvc, refs) = scanBodySignals(bodySyntax)

        let input = SymbolInput(
            symbol_kind: "deinitializer",
            ast_path: ["SourceFile"] + typeStack.map { "\($0)Decl" } + ["DeinitializerDecl"],
            access_level: access,
            modifiers: modifiers,
            attributes: attrs,
            type_signature: sig,
            inherits: [],
            conforms: [],
            is_protocol_requirement_impl: false,
            override_depth: 0,
            extension_of: nil,
            extension_file_count_same_name: 0,
            calls_out: calls,
            called_by: [],
            references: refs,
            keypath_refs: kps,
            selector_refs: sels,
            kvc_kvo_strings: kvc,
            ffi_names: ffiNames,
            is_coredata_nsmanaged: isCoreData,
            is_swiftdata_model: isSwiftData,
            codable_synthesized: false,
            is_ffi_entry: isFfi,
            is_objc_exposed: isObjc,
            cross_module_refs: false
        )
        let rec = SymbolRecord(symbol_id: symbolID, symbol_name: "\(qualName)(\(sig))", input: input, decision: nil)
        decisions.deinitializers.append(rec)
        return .visitChildren
    }

    override func visit(_ node: SubscriptDeclSyntax) -> SyntaxVisitorContinueKind {
        let modifiers = collectModifiers(node.modifiers)
        let attrs = collectAttributes(node.attributes)
        let (isObjc, isCoreData, isSwiftData, isFfi, ffiNames) = baseAttributesFlags(attrs, modifiers: modifiers)
        let access = accessLevel(from: node.modifiers)
        let sig = subscriptSignature(node)

        let qualName = qualTypeName(stack: typeStack, currentType: nil) + ".subscript"
        let symbolID = symbolID(of: node)

        let bodySyntax: Syntax = node.accessorBlock.map { Syntax($0) } ?? Syntax(node)
        let (calls, kps, sels, kvc, refs) = scanBodySignals(bodySyntax)

        let input = SymbolInput(
            symbol_kind: "subscript",
            ast_path: ["SourceFile"] + typeStack.map { "\($0)Decl" } + ["SubscriptDecl"],
            access_level: access,
            modifiers: modifiers,
            attributes: attrs,
            type_signature: sig,
            inherits: [],
            conforms: [],
            is_protocol_requirement_impl: false,
            override_depth: 0,
            extension_of: nil,
            extension_file_count_same_name: 0,
            calls_out: calls,
            called_by: [],
            references: refs,
            keypath_refs: kps,
            selector_refs: sels,
            kvc_kvo_strings: kvc,
            ffi_names: ffiNames,
            is_coredata_nsmanaged: isCoreData,
            is_swiftdata_model: isSwiftData,
            codable_synthesized: false,
            is_ffi_entry: isFfi,
            is_objc_exposed: isObjc,
            cross_module_refs: false
        )
        let rec = SymbolRecord(symbol_id: symbolID, symbol_name: "\(qualName)(\(sig))", input: input, decision: nil)
        decisions.subscripts.append(rec)
        return .visitChildren
    }

    override func visit(_ node: VariableDeclSyntax) -> SyntaxVisitorContinueKind {
        let modifiers = collectModifiers(node.modifiers)
        let attrs = collectAttributes(node.attributes)
        let (isObjc, isCoreData, isSwiftData, isFfi, ffiNames) = baseAttributesFlags(attrs, modifiers: modifiers)
        let access = accessLevel(from: node.modifiers)
        let sig = varTypeSignature(node)
        let names = propertyNames(node)

        let (calls, kps, sels, kvc, refs): ([String],[String],[String],[String],[String]) = {
            if let accessor = node.bindings.first?.accessorBlock {
                return scanBodySignals(Syntax(accessor))
            } else { return ([],[],[],[],[]) }
        }()

        let symbolID = symbolID(of: node)
        let qualPrefix = qualTypeName(stack: typeStack, currentType: nil)
        let isGlobal = typeStack.isEmpty
        let kind = isGlobal ? "variable" : "property"

        for n in names {
            let qn = (qualPrefix.isEmpty ? "" : "\(qualPrefix).") + n
            let input = SymbolInput(
                symbol_kind: kind,
                ast_path: ["SourceFile"] + (typeStack.map { "\($0)Decl" }) + ["VariableDecl"],
                access_level: access,
                modifiers: modifiers,
                attributes: attrs,
                type_signature: sig,
                inherits: [],
                conforms: [],
                is_protocol_requirement_impl: false,
                override_depth: 0,
                extension_of: nil,
                extension_file_count_same_name: 0,
                calls_out: calls,
                called_by: [],
                references: refs,
                keypath_refs: kps,
                selector_refs: sels,
                kvc_kvo_strings: kvc,
                ffi_names: ffiNames,
                is_coredata_nsmanaged: isCoreData,
                is_swiftdata_model: isSwiftData,
                codable_synthesized: false,
                is_ffi_entry: isFfi,
                is_objc_exposed: isObjc,
                cross_module_refs: false
            )
            let rec = SymbolRecord(symbol_id: symbolID, symbol_name: qn, input: input, decision: nil)
            if isGlobal { decisions.variables.append(rec) } else { decisions.properties.append(rec) }
        }
        return .visitChildren
    }

    override func visit(_ node: EnumCaseDeclSyntax) -> SyntaxVisitorContinueKind {
        let modifiers = collectModifiers(node.modifiers)
        let attrs = collectAttributes(node.attributes)
        let (isObjc, isCoreData, isSwiftData, isFfi, ffiNames) = baseAttributesFlags(attrs, modifiers: modifiers)
        let access = accessLevel(from: node.modifiers)

        for elem in node.elements {
            let name = elem.name.text
            let qualName = qualTypeName(stack: typeStack, currentType: nil) + ".\(name)"
            let symbolID = symbolID(of: node)
            let input = SymbolInput(
                symbol_kind: "enumCase",
                ast_path: ["SourceFile"] + typeStack.map { "\($0)Decl" } + ["EnumCaseDecl"],
                access_level: access,
                modifiers: modifiers,
                attributes: attrs,
                type_signature: "",
                inherits: [],
                conforms: [],
                is_protocol_requirement_impl: false,
                override_depth: 0,
                extension_of: nil,
                extension_file_count_same_name: 0,
                calls_out: [],
                called_by: [],
                references: [],
                keypath_refs: [],
                selector_refs: [],
                kvc_kvo_strings: [],
                ffi_names: ffiNames,
                is_coredata_nsmanaged: isCoreData,
                is_swiftdata_model: isSwiftData,
                codable_synthesized: false,
                is_ffi_entry: isFfi,
                is_objc_exposed: isObjc,
                cross_module_refs: false
            )
            let rec = SymbolRecord(symbol_id: symbolID, symbol_name: qualName, input: input, decision: nil)
            decisions.enumCases.append(rec)
        }
        return .visitChildren
    }
}

// MARK: - Runner

func swiftFiles(under path: String) -> [String] {
    var results: [String] = []
    let fm = FileManager.default
    var isDir: ObjCBool = false
    guard fm.fileExists(atPath: path, isDirectory: &isDir) else { return [] }
    if !isDir.boolValue {
        if path.hasSuffix(".swift") { return [path] } else { return [] }
    }
    let enumerator = fm.enumerator(atPath: path)
    while let item = enumerator?.nextObject() as? String {
        if item.hasSuffix(".swift") {
            results.append((path as NSString).appendingPathComponent(item))
        }
    }
    return results
}

func buildOutputJSON(for paths: [String]) -> OutputJSON {
    let ctx = prepassCountExtensions(filePaths: paths)

    var merged = Decisions()
    for p in paths {
        guard let source = try? String(contentsOfFile: p, encoding: .utf8) else { continue }
        let collector = SymbolCollector(filePath: p, source: source, projectCtx: ctx)
        collector.walk(Parser.parse(source: source))

        func appendAll<T>(_ src: [T], _ dst: inout [T]) { dst.append(contentsOf: src) }
        appendAll(collector.decisions.classes, &merged.classes)
        appendAll(collector.decisions.structs, &merged.structs)
        appendAll(collector.decisions.enums, &merged.enums)
        appendAll(collector.decisions.protocols, &merged.protocols)
        appendAll(collector.decisions.extensions, &merged.extensions)
        appendAll(collector.decisions.methods, &merged.methods)
        appendAll(collector.decisions.properties, &merged.properties)
        appendAll(collector.decisions.variables, &merged.variables)
        appendAll(collector.decisions.enumCases, &merged.enumCases)
        appendAll(collector.decisions.initializers, &merged.initializers)
        appendAll(collector.decisions.deinitializers, &merged.deinitializers)
        appendAll(collector.decisions.subscripts, &merged.subscripts)
    }

    let meta = Meta(
        tool: "obfuscation_exclude_assistant",
        model: "deepseek-coder-7b-lora",
        prompt_context:
"""
Symbols should generally be organized into their corresponding arrays (classes, structs, enums, ...). However, the grouping structure may be adjusted if necessary.
"""
    )
    return OutputJSON(meta: meta, decisions: merged)
}

// MARK: - Main

if CommandLine.arguments.count < 2 {
    fputs("Usage: \(CommandLine.arguments[0]) <path-or-file> [<more-paths>...]\n", stderr)
    exit(1)
}

let inputPaths = Array(CommandLine.arguments.dropFirst()).flatMap { swiftFiles(under: $0) }
let out = buildOutputJSON(for: inputPaths)

let data = try JSONSerialization.data(withJSONObject: JSONEncoderFriendly.encode(out), options: [.prettyPrinted])
if let s = String(data: data, encoding: .utf8) { print(s) }

// Helper to encode Codable → JSON (sorted keys 생략, 간단 라운드트립)
enum JSONEncoderFriendly {
    static func encode<T: Encodable>(_ value: T) -> Any {
        let enc = JSONEncoder()
        do {
            let data = try enc.encode(value)
            return try JSONSerialization.jsonObject(with: data, options: [])
        } catch {
            fatalError("Encoding failed: \(error)")
        }
    }
}