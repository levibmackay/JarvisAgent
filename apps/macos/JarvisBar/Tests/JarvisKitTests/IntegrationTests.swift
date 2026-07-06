import Foundation
import Testing

@testable import JarvisKit

/// End-to-end against a live local server: JARVIS_INTEGRATION=1 swift test
/// (start `jarvis-server` first). Works without Anthropic credentials — the
/// turn then ends with an `error` event, which still exercises the full
/// HTTP + SSE path.
@Suite(.enabled(if: ProcessInfo.processInfo.environment["JARVIS_INTEGRATION"] == "1"))
struct IntegrationTests {
    @Test func fullSessionRoundTrip() async throws {
        let client = try JarvisClient(token: JarvisClient.loadToken())
        try await client.health()

        let sessionID = try await client.createSession()
        var events: [AgentEvent] = []
        for try await event in client.send(sessionID: sessionID, text: "hi") {
            events.append(event)
        }
        let last = try #require(events.last)
        switch last {
        case .done, .error: break
        default: Issue.record("stream ended with \(last), expected done/error")
        }

        try await client.deleteSession(sessionID)
        await #expect(throws: JarvisClientError.self) {
            try await client.deleteSession(sessionID)  // now 404
        }
    }
}
