import AppKit
import AVFoundation
import Speech
import WebKit

private let bundleID = "ai.theopadilha.jarvis.cockpit"
private let fallbackURL = "https://jarvis-theo.vercel.app/fala?app=1"

@main
enum Jarvis {
    static func main() {
        let mine = ProcessInfo.processInfo.processIdentifier
        let others = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID)
            .filter { $0.processIdentifier != mine }
        if let existing = others.first {
            existing.activate(options: [.activateAllWindows])
            return
        }
        let app = NSApplication.shared
        let delegate = AppDelegate()
        AppDelegate.shared = delegate
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.activate(ignoringOtherApps: true)
        app.run()
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate, WKScriptMessageHandler, AVSpeechSynthesizerDelegate, AVAudioPlayerDelegate {
    static var shared: AppDelegate?
    private var window: NSWindow?
    private var webView: WKWebView?
    private let synth = AVSpeechSynthesizer()
    private var player: AVAudioPlayer?
    private var speakDone: (() -> Void)?
    private var wantListen = false
    private var recognizer: SFSpeechRecognizer?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private let engine = AVAudioEngine()
    private var tapInstalled = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        synth.delegate = self
        recognizer = SFSpeechRecognizer(locale: Locale(identifier: "pt-BR"))
        let window = makeWindow()
        let webView = makeWebView()
        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        self.window = window
        self.webView = webView
        webView.load(URLRequest(url: cockpitURL()))
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window?.makeKeyAndOrderFront(nil)
        return true
    }

    func webView(
        _ webView: WKWebView,
        requestMediaCapturePermissionFor origin: WKSecurityOrigin,
        initiatedByFrame frame: WKFrameInfo,
        type: WKMediaCaptureType,
        decisionHandler: @escaping (WKPermissionDecision) -> Void
    ) {
        decisionHandler(.grant)
    }

    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        if let url = navigationAction.request.url {
            NSWorkspace.shared.open(url)
        }
        return nil
    }

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.allow)
            return
        }
        let host = url.host?.lowercased() ?? ""
        let home = cockpitURL().host?.lowercased() ?? "jarvis-theo.vercel.app"
        let popup = navigationAction.targetFrame == nil
        let click = navigationAction.navigationType == .linkActivated
        if (popup || click) && host != home && !host.hasSuffix("." + home) {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        let body = String(describing: message.body)
        if message.name == "jarvisSpeak" {
            speakNative(body)
        } else if message.name == "jarvisListen" {
            if body == "start" {
                startListen()
            } else {
                stopListen()
            }
        }
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        finishSpeak()
    }

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        finishSpeak()
    }

    private func speakNative(_ raw: String) {
        let text = String(raw.prefix(220)).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else {
            finishSpeak()
            return
        }
        stopListen()
        synth.stopSpeaking(at: .immediate)
        player?.stop()
        fetchPocketTTS(text) { [weak self] data in
            DispatchQueue.main.async {
                guard let self else { return }
                if let data, self.playAudio(data) { return }
                self.speakAV(text)
            }
        }
    }

    private func fetchPocketTTS(_ text: String, done: @escaping (Data?) -> Void) {
        guard let url = URL(string: "http://127.0.0.1:8123/speech") else {
            done(nil)
            return
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.timeoutInterval = 8
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["text": text, "persona": "jarvis"])
        URLSession.shared.dataTask(with: req) { data, response, _ in
            let ok = (response as? HTTPURLResponse)?.statusCode == 200
            done(ok && (data?.count ?? 0) > 44 ? data : nil)
        }.resume()
    }

    private func playAudio(_ data: Data) -> Bool {
        do {
            let player = try AVAudioPlayer(data: data)
            player.delegate = self
            self.player = player
            return player.play()
        } catch {
            return false
        }
    }

    private func speakAV(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "pt-BR")
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate
        utterance.pitchMultiplier = 1.02
        synth.speak(utterance)
    }

    private func finishSpeak() {
        webView?.evaluateJavaScript("window.__jarvisOnSpeakDone && window.__jarvisOnSpeakDone()", completionHandler: nil)
        if wantListen {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { [weak self] in
                self?.beginRecognition()
            }
        }
    }

    private func startListen() {
        wantListen = true
        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            DispatchQueue.main.async {
                guard status == .authorized else { return }
                self?.beginRecognition()
            }
        }
    }

    private func stopListen() {
        wantListen = false
        task?.cancel()
        task = nil
        request?.endAudio()
        request = nil
        if tapInstalled {
            engine.inputNode.removeTap(onBus: 0)
            tapInstalled = false
        }
        if engine.isRunning { engine.stop() }
    }

    private func beginRecognition() {
        guard wantListen, let recognizer, recognizer.isAvailable else { return }
        task?.cancel()
        request?.endAudio()
        if tapInstalled {
            engine.inputNode.removeTap(onBus: 0)
            tapInstalled = false
        }
        if engine.isRunning { engine.stop() }
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = false
        self.request = request
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
            request.append(buffer)
        }
        tapInstalled = true
        engine.prepare()
        do {
            try engine.start()
        } catch {
            return
        }
        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }
            if let text = result?.bestTranscription.formattedString, result?.isFinal == true, !text.isEmpty {
                self.deliverHeard(text)
            }
            if error != nil || result?.isFinal == true {
                DispatchQueue.main.async {
                    if self.wantListen {
                        self.beginRecognition()
                    }
                }
            }
        }
    }

    private func deliverHeard(_ text: String) {
        guard let data = try? JSONSerialization.data(withJSONObject: [text], options: []),
              let wrapped = String(data: data, encoding: .utf8) else { return }
        let arg = String(wrapped.dropFirst().dropLast())
        webView?.evaluateJavaScript("window.__jarvisNativeHeard && window.__jarvisNativeHeard(\(arg))", completionHandler: nil)
    }

    private func cockpitURL() -> URL {
        let raw = (
            ProcessInfo.processInfo.environment["JARVIS_COCKPIT_URL"]
            ?? Bundle.main.object(forInfoDictionaryKey: "JarvisCockpitURL") as? String
            ?? fallbackURL
        ).trimmingCharacters(in: .whitespacesAndNewlines)
        return URL(string: raw) ?? URL(string: fallbackURL)!
    }

    private func makeWindow() -> NSWindow {
        let size = NSSize(width: 280, height: 380)
        let rect = cornerFrame(size)
        let window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "JARVIS"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.isMovableByWindowBackground = true
        window.level = .floating
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        window.setFrameAutosaveName("")
        window.setFrame(rect, display: true)
        window.backgroundColor = NSColor(calibratedRed: 0.03, green: 0.02, blue: 0.05, alpha: 1)
        return window
    }

    private func makeWebView() -> WKWebView {
        let config = WKWebViewConfiguration()
        config.mediaTypesRequiringUserActionForPlayback = []
        config.websiteDataStore = .default()
        config.userContentController.add(self, name: "jarvisSpeak")
        config.userContentController.add(self, name: "jarvisListen")
        if #available(macOS 11.0, *) {
            config.defaultWebpagePreferences.allowsContentJavaScript = true
        }
        let view = WKWebView(frame: .zero, configuration: config)
        view.uiDelegate = self
        view.navigationDelegate = self
        view.allowsBackForwardNavigationGestures = false
        view.setValue(false, forKey: "drawsBackground")
        return view
    }

    private func cornerFrame(_ size: NSSize) -> NSRect {
        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        let x = screen.maxX - size.width - 12
        let y = screen.maxY - size.height - 8
        return NSRect(x: x, y: y, width: size.width, height: size.height)
    }
}
