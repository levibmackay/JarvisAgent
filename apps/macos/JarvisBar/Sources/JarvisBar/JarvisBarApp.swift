import SwiftUI

@main
struct JarvisBarApp: App {
    @StateObject private var model = ChatModel()

    var body: some Scene {
        MenuBarExtra("Jarvis", systemImage: "bolt.circle") {
            ChatView(model: model)
        }
        .menuBarExtraStyle(.window)
    }
}
