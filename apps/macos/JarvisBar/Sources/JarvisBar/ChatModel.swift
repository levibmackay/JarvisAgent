import Foundation
import JarvisKit

@MainActor
final class ChatModel: ObservableObject {
    struct Entry: Identifiable {
        enum Kind { case user, assistant, tool, error }
        let id = UUID()
        let kind: Kind
        var text: String
    }

    @Published var entries: [Entry] = []
    @Published var draft = ""
    @Published var isBusy = false
    @Published var pendingConsent: ConsentRequest?
    @Published var statusMessage: String?

    private var client: JarvisClient?
    private var sessionID: String?

    /// Lazily connect: load the token and create a session on first use,
    /// so launching the app before the server doesn't hard-fail.
    private func connectedClient() async throws -> (JarvisClient, String) {
        if let client, let sessionID { return (client, sessionID) }
        let client = try JarvisClient(token: JarvisClient.loadToken())
        let sessionID = try await client.createSession()
        self.client = client
        self.sessionID = sessionID
        return (client, sessionID)
    }

    func send() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isBusy else { return }
        draft = ""
        entries.append(Entry(kind: .user, text: text))
        isBusy = true
        statusMessage = nil

        Task {
            do {
                let (client, sessionID) = try await connectedClient()
                for try await event in client.send(sessionID: sessionID, text: text) {
                    handle(event)
                }
            } catch {
                statusMessage = error.localizedDescription
                // Session may be gone (server restart); reconnect next send.
                sessionID = nil
            }
            isBusy = false
            pendingConsent = nil
        }
    }

    private func handle(_ event: AgentEvent) {
        switch event {
        case .text(let chunk):
            if case .assistant = entries.last?.kind {
                entries[entries.count - 1].text += chunk
            } else {
                entries.append(Entry(kind: .assistant, text: chunk))
            }
        case .toolUse(let tool, let params):
            pendingConsent = nil  // answered (or timed out) if the tool ran
            entries.append(Entry(kind: .tool, text: "\(tool) \(params)"))
        case .consentRequest(let request):
            pendingConsent = request
        case .done:
            pendingConsent = nil
        case .error(let message):
            entries.append(Entry(kind: .error, text: message))
        }
    }

    func respondToConsent(allow: Bool) {
        guard let request = pendingConsent, let client, let sessionID else { return }
        pendingConsent = nil
        Task {
            do {
                try await client.resolveConsent(
                    sessionID: sessionID, consentID: request.id, allow: allow)
            } catch {
                statusMessage = "Consent reply failed: \(error.localizedDescription)"
            }
        }
    }

    func clearConversation() {
        guard !isBusy else { return }
        entries = []
        statusMessage = nil
        if let client, let sessionID {
            Task { try? await client.deleteSession(sessionID) }
        }
        sessionID = nil
    }
}
