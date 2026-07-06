// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "JarvisBar",
    platforms: [.macOS(.v14)],
    targets: [
        // API client + SSE parsing — UI-free so it can be unit tested
        // and reused by the future iPhone app.
        .target(name: "JarvisKit"),
        .executableTarget(name: "JarvisBar", dependencies: ["JarvisKit"]),
        .testTarget(name: "JarvisKitTests", dependencies: ["JarvisKit"]),
    ]
)
