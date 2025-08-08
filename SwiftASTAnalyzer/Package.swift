// swift-tools-version: 5.7

import PackageDescription

let package = Package(
    name: "SwiftASTAnalyzer",
    platforms: [
        .macOS(.v10_15),
    ],
    products: [
        .executable(
            name: "swift-ast-analyzer",
            targets: ["SwiftASTAnalyzer"]
        ),
    ],
    dependencies: [
        .package(
            url: "https://github.com/apple/swift-syntax.git",
            from: "509.0.0"
        ),
    ],
    targets: [
        .executableTarget(
            name: "SwiftASTAnalyzer",
            dependencies: [
                .product(name: "SwiftSyntax", package: "swift-syntax"),
                .product(name: "SwiftParser", package: "swift-syntax"),
            ],
            path: "Sources"
        )
    ]
)
