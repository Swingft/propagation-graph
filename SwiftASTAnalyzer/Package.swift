// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SwiftASTAnalyzer",
    platforms: [
        .macOS(.v12)
    ],
    products: [
        .executable(name: "swift-ast-analyzer", targets: ["swift-ast-analyzer"])
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-syntax.git", exact: "600.0.0")
    ],
    targets: [
        .executableTarget(
            name: "swift-ast-analyzer",
            // 'dependencies'를 'path'보다 앞으로 이동하여 오류를 해결합니다.
            dependencies: [
                .product(name: "SwiftSyntax", package: "swift-syntax"),
                .product(name: "SwiftParser", package: "swift-syntax"),
            ],
            path: "Sources",
            exclude: [],
            sources: nil,
            resources: []
        )
    ]
)