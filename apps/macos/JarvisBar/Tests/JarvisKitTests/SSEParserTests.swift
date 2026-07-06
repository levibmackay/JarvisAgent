import Foundation
import Testing

@testable import JarvisKit

@Suite struct SSEParserTests {
    let parser = SSEParser()

    @Test func parsesTextEvent() {
        let event = parser.feed(line: #"data: {"type": "text", "text": "Hi"}"#)
        #expect(event == .text("Hi"))
    }

    @Test func ignoresEventAndBlankLines() {
        #expect(parser.feed(line: "event: text") == nil)
        #expect(parser.feed(line: "") == nil)
        #expect(parser.feed(line: ": comment") == nil)
    }

    @Test func parsesConsentRequest() {
        let line = #"data: {"type": "consent_request", "consent_id": "abc", "# +
            #""tool": "shell", "params": {"command": "rm x"}, "risk": "destructive", "# +
            #""timeout_seconds": 300.0}"#
        let event = parser.feed(line: line)
        #expect(event == .consentRequest(ConsentRequest(
            id: "abc", tool: "shell", params: #"{"command":"rm x"}"#,
            risk: "destructive")))
    }

    @Test func parsesToolUseDoneAndError() {
        #expect(parser.feed(line: #"data: {"type": "tool_use", "tool": "get_time", "params": {}}"#)
            == .toolUse(tool: "get_time", params: "{}"))
        #expect(parser.feed(line: #"data: {"type": "done", "reply": "Done."}"#)
            == .done(reply: "Done."))
        #expect(parser.feed(line: #"data: {"type": "error", "message": "boom"}"#)
            == .error(message: "boom"))
    }

    @Test func unknownTypeAndMalformedJSONAreDropped() {
        #expect(parser.feed(line: #"data: {"type": "future_thing"}"#) == nil)
        #expect(parser.feed(line: "data: {not json") == nil)
    }

    @Test func unicodeSurvivesRoundTrip() {
        let event = parser.feed(line: #"data: {"type": "text", "text": "héllo 👋"}"#)
        #expect(event == .text("héllo 👋"))
    }
}
