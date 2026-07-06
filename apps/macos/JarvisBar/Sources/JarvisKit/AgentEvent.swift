import Foundation

/// One server-sent event from a Jarvis turn stream.
public enum AgentEvent: Equatable, Sendable {
    case text(String)
    case toolUse(tool: String, params: String)
    case consentRequest(ConsentRequest)
    case done(reply: String)
    case error(message: String)
}

public struct ConsentRequest: Equatable, Sendable {
    public let id: String
    public let tool: String
    public let params: String
    public let risk: String
}

extension AgentEvent {
    /// Parse the JSON payload of one SSE `data:` line. Returns nil for
    /// unknown event types so newer servers don't break older clients.
    public static func parse(data: Data) -> AgentEvent? {
        guard let object = try? JSONSerialization.jsonObject(with: data),
              let fields = object as? [String: Any],
              let type = fields["type"] as? String
        else { return nil }

        switch type {
        case "text":
            return .text(fields["text"] as? String ?? "")
        case "tool_use":
            return .toolUse(tool: fields["tool"] as? String ?? "?",
                            params: prettyParams(fields["params"]))
        case "consent_request":
            return .consentRequest(ConsentRequest(
                id: fields["consent_id"] as? String ?? "",
                tool: fields["tool"] as? String ?? "?",
                params: prettyParams(fields["params"]),
                risk: fields["risk"] as? String ?? "unknown"))
        case "done":
            return .done(reply: fields["reply"] as? String ?? "")
        case "error":
            return .error(message: fields["message"] as? String ?? "unknown error")
        default:
            return nil
        }
    }

    private static func prettyParams(_ value: Any?) -> String {
        guard let value,
              JSONSerialization.isValidJSONObject(value),
              let data = try? JSONSerialization.data(
                  withJSONObject: value, options: [.sortedKeys])
        else { return "{}" }
        return String(decoding: data, as: UTF8.self)
    }
}
