import JarvisKit
import SwiftUI

struct ChatView: View {
    @ObservedObject var model: ChatModel
    @FocusState private var inputFocused: Bool

    var body: some View {
        VStack(spacing: 8) {
            header
            transcript
            if let consent = model.pendingConsent {
                ConsentCard(request: consent) { model.respondToConsent(allow: $0) }
            }
            if let status = model.statusMessage {
                Text(status)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            inputBar
        }
        .padding(10)
        .frame(width: 380, height: 480)
    }

    private var header: some View {
        HStack {
            Text("Jarvis").font(.headline)
            Spacer()
            Button("Clear", action: model.clearConversation)
                .disabled(model.isBusy || model.entries.isEmpty)
            Button("Quit") { NSApp.terminate(nil) }
        }
        .buttonStyle(.borderless)
        .font(.caption)
    }

    private var transcript: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 6) {
                    ForEach(model.entries) { EntryRow(entry: $0) }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .onChange(of: model.entries.last?.text) {
                if let last = model.entries.last { proxy.scrollTo(last.id) }
            }
        }
    }

    private var inputBar: some View {
        HStack {
            TextField("Ask Jarvis…", text: $model.draft)
                .textFieldStyle(.roundedBorder)
                .focused($inputFocused)
                .onSubmit(model.send)
            if model.isBusy {
                ProgressView().controlSize(.small)
            } else {
                Button("Send", action: model.send)
                    .disabled(model.draft.trimmingCharacters(
                        in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .onAppear { inputFocused = true }
    }
}

private struct EntryRow: View {
    let entry: ChatModel.Entry

    var body: some View {
        switch entry.kind {
        case .user:
            Text(entry.text)
                .padding(6)
                .background(.blue.opacity(0.15), in: RoundedRectangle(cornerRadius: 6))
                .frame(maxWidth: .infinity, alignment: .trailing)
        case .assistant:
            Text(entry.text)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
        case .tool:
            Label(entry.text, systemImage: "wrench")
                .font(.caption.monospaced())
                .foregroundStyle(.secondary)
                .lineLimit(2)
        case .error:
            Label(entry.text, systemImage: "exclamationmark.triangle")
                .font(.caption)
                .foregroundStyle(.red)
        }
    }
}

private struct ConsentCard: View {
    let request: ConsentRequest
    let respond: (Bool) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("Jarvis wants to run **\(request.tool)** (\(request.risk))",
                  systemImage: "hand.raised")
                .font(.callout)
            Text(request.params)
                .font(.caption.monospaced())
                .lineLimit(4)
                .foregroundStyle(.secondary)
            HStack {
                Spacer()
                Button("Deny", role: .cancel) { respond(false) }
                Button("Allow") { respond(true) }
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(8)
        .background(.yellow.opacity(0.15), in: RoundedRectangle(cornerRadius: 8))
    }
}
