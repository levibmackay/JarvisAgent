import Foundation

/// Line-based parser for the Jarvis SSE stream.
///
/// The server emits one single-line JSON payload per event and repeats the
/// event type inside the JSON, so each `data:` line is a complete event on
/// its own. Parsing per data line (instead of waiting for the blank-line
/// separator) also sidesteps AsyncLineSequence's habit of swallowing empty
/// lines.
public struct SSEParser: Sendable {
    public init() {}

    /// Feed one line (without its trailing newline); returns an event for
    /// `data:` lines, nil otherwise.
    public func feed(line: String) -> AgentEvent? {
        guard line.hasPrefix("data:") else { return nil }
        let payload = line.dropFirst("data:".count).drop(while: { $0 == " " })
        return AgentEvent.parse(data: Data(payload.utf8))
    }
}
