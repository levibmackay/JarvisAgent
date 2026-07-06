import Foundation

public enum JarvisClientError: Error, LocalizedError {
    case tokenMissing(String)
    case httpStatus(Int)
    case invalidResponse

    public var errorDescription: String? {
        switch self {
        case .tokenMissing(let path):
            return "No server token at \(path) — is jarvis-server running?"
        case .httpStatus(let code):
            return "Server returned HTTP \(code)"
        case .invalidResponse:
            return "Unexpected response from server"
        }
    }
}

/// Async client for the local Jarvis API (see README: API server).
public struct JarvisClient: Sendable {
    public let baseURL: URL
    private let token: String
    private let session: URLSession

    public static let defaultTokenPath =
        NSString(string: "~/.jarvis/server.token").expandingTildeInPath

    public init(baseURL: URL = URL(string: "http://127.0.0.1:8765")!,
                token: String,
                session: URLSession = .shared) {
        self.baseURL = baseURL
        self.token = token
        self.session = session
    }

    public static func loadToken(path: String = defaultTokenPath) throws -> String {
        guard let raw = try? String(contentsOfFile: path, encoding: .utf8),
              !raw.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        else { throw JarvisClientError.tokenMissing(path) }
        return raw.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // MARK: - Requests

    private func request(_ method: String, _ path: String,
                         body: (some Encodable)? = nil as String?) throws -> URLRequest {
        var request = URLRequest(url: baseURL.appending(path: path))
        request.httpMethod = method
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(body)
        }
        return request
    }

    private static func check(_ response: URLResponse, allowing codes: Range<Int>) throws {
        guard let http = response as? HTTPURLResponse else {
            throw JarvisClientError.invalidResponse
        }
        guard codes.contains(http.statusCode) else {
            throw JarvisClientError.httpStatus(http.statusCode)
        }
    }

    public func health() async throws {
        let (_, response) = try await session.data(
            for: request("GET", "/v1/health"))
        try Self.check(response, allowing: 200..<300)
    }

    public func createSession() async throws -> String {
        struct SessionOut: Decodable { let session_id: String }
        let (data, response) = try await session.data(
            for: request("POST", "/v1/sessions"))
        try Self.check(response, allowing: 200..<300)
        return try JSONDecoder().decode(SessionOut.self, from: data).session_id
    }

    public func deleteSession(_ id: String) async throws {
        let (_, response) = try await session.data(
            for: request("DELETE", "/v1/sessions/\(id)"))
        try Self.check(response, allowing: 200..<300)
    }

    public func resolveConsent(sessionID: String, consentID: String,
                               allow: Bool) async throws {
        struct ConsentIn: Encodable { let allow: Bool }
        let (_, response) = try await session.data(
            for: request("POST", "/v1/sessions/\(sessionID)/consent/\(consentID)",
                         body: ConsentIn(allow: allow)))
        try Self.check(response, allowing: 200..<300)
    }

    /// Send one user message; the returned stream yields events until the
    /// turn finishes (`done` or `error` is the last event).
    public func send(sessionID: String, text: String)
        -> AsyncThrowingStream<AgentEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    struct MessageIn: Encodable { let text: String }
                    let (bytes, response) = try await session.bytes(
                        for: request("POST", "/v1/sessions/\(sessionID)/messages",
                                     body: MessageIn(text: text)))
                    try Self.check(response, allowing: 200..<300)
                    let parser = SSEParser()
                    for try await line in bytes.lines {
                        if let event = parser.feed(line: line) {
                            continuation.yield(event)
                        }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}
