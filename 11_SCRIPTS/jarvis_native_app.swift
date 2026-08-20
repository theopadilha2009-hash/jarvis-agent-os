import AppKit
import AVFoundation
import Speech
import WebKit

private let bundleID = "ai.theopadilha.jarvis.cockpit"
private let fallbackURL = "https://jarvis-theo.vercel.app/fala?app=1"

final class PCMConverter {
    func convert(_ buffer: AVAudioPCMBuffer, to format: AVAudioFormat) -> AVAudioPCMBuffer? {
        guard buffer.format != format else { return buffer }
        guard let converter = AVAudioConverter(from: buffer.format, to: format) else { return nil }
        let ratio = format.sampleRate / buffer.format.sampleRate
        let frames = AVAudioFrameCount((Double(buffer.frameLength) * ratio).rounded(.up) + 64)
        guard let output = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: max(frames, 1)) else { return nil }
        var error: NSError?
        var sent = false
        converter.convert(to: output, error: &error) { _, status in
            if sent {
                status.pointee = .endOfStream
                return nil
            }
            sent = true
            status.pointee = .haveData
            return buffer
        }
        if error != nil || output.frameLength == 0 { return nil }
        return output
    }
}

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

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate, WKScriptMessageHandler, AVSpeechSynthesizerDelegate, AVAudioPlayerDelegate, SFSpeechRecognizerDelegate {
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
    private var engine = AVAudioEngine()
    private var tapInstalled = false
    private var recycleTimer: Timer?
    private var retryTimer: Timer?
    private var napActivity: NSObjectProtocol?
    private var startingListen = false
    private var lastPartial = ""
    private var lastWasFinal = false
    private var useModern = false
    private var modernTask: Task<Void, Never>?
    private var resultsTask: Task<Void, Never>?
    private var analyzerFinish: (() -> Void)?

    func applicationDidFinishLaunching(_ notification: Notification) {
        synth.delegate = self
        recognizer = SFSpeechRecognizer(locale: Locale(identifier: "pt-BR"))
            ?? SFSpeechRecognizer(locale: Locale(identifier: "pt-PT"))
            ?? SFSpeechRecognizer()
        recognizer?.delegate = self
        napActivity = ProcessInfo.processInfo.beginActivity(
            options: [.userInitiatedAllowingIdleSystemSleep],
            reason: "JARVIS always listening"
        )
        let window = makeWindow()
        let webView = makeWebView()
        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        self.window = window
        self.webView = webView
        webView.load(URLRequest(url: cockpitURL()))
        UserDefaults.standard.set(false, forKey: "NSQuitAlwaysKeepsWindows")
        DispatchQueue.main.async { [weak self] in
            self?.startListen()
            self?.scheduleRecycle()
        }
    }

    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool { false }

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
            } else if body == "restart" {
                restartListen()
            } else {
                stopListen()
            }
        } else if message.name == "jarvisRestart" {
            webView?.reloadFromOrigin()
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

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        if wantListen { startListen() }
    }

    func speechRecognizer(_ speechRecognizer: SFSpeechRecognizer, availabilityDidChange available: Bool) {
        logListen("available \(available)")
        guard available, wantListen, !useModern else { return }
        if engine.isRunning, task != nil { return }
        scheduleRetry()
    }

    private func finishSpeak() {
        webView?.evaluateJavaScript("window.__jarvisOnSpeakDone && window.__jarvisOnSpeakDone()", completionHandler: nil)
        if wantListen {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { [weak self] in
                self?.startListen()
            }
        }
    }

    private func startListen() {
        wantListen = true
        logListen("startListen")
        if #available(macOS 26.0, *), SpeechTranscriber.isAvailable {
            if modernTask != nil, engine.isRunning { return }
            startModernListen()
            return
        }
        if engine.isRunning, task != nil, tapInstalled { return }
        requestSpeechThenRecognize()
    }

    private func restartListen() {
        wantListen = true
        lastPartial = ""
        lastWasFinal = true
        stopModern()
        tearDownRecognition()
        startListen()
    }

    private func stopModern() {
        analyzerFinish?()
        analyzerFinish = nil
        modernTask?.cancel()
        resultsTask?.cancel()
        modernTask = nil
        resultsTask = nil
        useModern = false
    }

    @available(macOS 26.0, *)
    private func startModernListen() {
        useModern = true
        stopModern()
        useModern = true
        wantListen = true
        modernTask = Task { [weak self] in
            await self?.runModernListen()
        }
    }

    @available(macOS 26.0, *)
    private func runModernListen() async {
        logListen("modern start")
        tellJS("waiting")
        let preferred = Locale(identifier: "pt-BR")
        let locale = await SpeechTranscriber.supportedLocale(equivalentTo: preferred) ?? preferred
        let transcriber = SpeechTranscriber(
            locale: locale,
            transcriptionOptions: [],
            reportingOptions: [.volatileResults, .fastResults],
            attributeOptions: []
        )
        do {
            let status = await AssetInventory.status(forModules: [transcriber])
            logListen("asset \(String(describing: status))")
            if status != .installed {
                tellJS("waiting")
                if let request = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
                    try await request.downloadAndInstall()
                }
            }
            _ = try? await AssetInventory.reserve(locale: locale)
        } catch {
            logListen("asset error \(error)")
        }
        let analyzerFormat = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [transcriber])
        let analyzer = SpeechAnalyzer(modules: [transcriber])
        let context = AnalysisContext()
        context.contextualStrings = [.general: ["Jarvis", "oi Jarvis", "Olá Jarvis", "fala Jarvis", "Ultron"]]
        try? await analyzer.setContext(context)
        let (stream, continuation) = AsyncStream.makeStream(of: AnalyzerInput.self)
        analyzerFinish = { continuation.finish() }
        resultsTask = Task { [weak self] in
            do {
                for try await result in transcriber.results {
                    let text = String(result.text.characters)
                    guard !text.isEmpty else { continue }
                    let isFinal = result.isFinal
                    await MainActor.run {
                        self?.deliverHeard(text, final: isFinal)
                    }
                }
            } catch {
                self?.logListen("results \(error)")
            }
        }
        await MainActor.run { [weak self] in
            self?.startMic(to: analyzerFormat) { buffer in
                continuation.yield(AnalyzerInput(buffer: buffer))
            }
        }
        tellJS("listening")
        logListen("modern listening")
        do {
            try await analyzer.start(inputSequence: stream)
        } catch {
            logListen("analyzer \(error)")
            if !Task.isCancelled {
                tellJS("error:\(error.localizedDescription)")
            }
        }
    }

    @available(macOS 26.0, *)
    private func startMic(to analyzerFormat: AVAudioFormat?, yield: @escaping (AVAudioPCMBuffer) -> Void) {
        tearDownRecognition()
        let input = engine.inputNode
        let micFormat = input.outputFormat(forBus: 0)
        guard micFormat.sampleRate > 0 else {
            logListen("bad mic format")
            scheduleRetry()
            return
        }
        let converter = PCMConverter()
        input.installTap(onBus: 0, bufferSize: 4096, format: micFormat) { [weak self] buffer, _ in
            self?.emitLevel(buffer)
            let out = analyzerFormat.flatMap { converter.convert(buffer, to: $0) } ?? buffer
            yield(out)
        }
        tapInstalled = true
        do {
            try engine.start()
            logListen("mic sr=\(micFormat.sampleRate)")
        } catch {
            logListen("engine \(error)")
            scheduleRetry()
        }
    }

    private func requestSpeechThenRecognize() {
        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            DispatchQueue.main.async {
                guard let self else { return }
                self.logListen("speech auth \(status.rawValue)")
                if status != .authorized {
                    self.tellJS("denied")
                    return
                }
                self.beginRecognition()
            }
        }
    }

    private func logListen(_ msg: String) {
        let line = "\(Date()) \(msg)\n"
        let path = "/tmp/jarvis-listen.log"
        if let handle = FileHandle(forWritingAtPath: path) {
            handle.seekToEndOfFile()
            handle.write(Data(line.utf8))
            handle.closeFile()
        } else {
            FileManager.default.createFile(atPath: path, contents: Data(line.utf8))
        }
    }

    private func stopListen() {
        wantListen = false
        stopModern()
        tearDownRecognition()
    }

    private func scheduleRecycle() {
        recycleTimer?.invalidate()
        recycleTimer = Timer.scheduledTimer(withTimeInterval: 40, repeats: true) { [weak self] _ in
            guard let self, self.wantListen, !self.useModern else { return }
            self.beginRecognition()
        }
    }

    private func scheduleRetry() {
        retryTimer?.invalidate()
        retryTimer = Timer.scheduledTimer(withTimeInterval: 2.5, repeats: false) { [weak self] _ in
            guard let self, self.wantListen else { return }
            self.startListen()
        }
    }

    private func tearDownRecognition() {
        if !lastWasFinal, !lastPartial.isEmpty {
            deliverHeard(lastPartial, final: true)
        }
        lastPartial = ""
        lastWasFinal = false
        task?.cancel()
        task = nil
        request?.endAudio()
        request = nil
        if tapInstalled {
            engine.inputNode.removeTap(onBus: 0)
            tapInstalled = false
        }
        if engine.isRunning { engine.stop() }
        engine.reset()
        engine = AVAudioEngine()
    }

    private func beginRecognition() {
        guard wantListen, !startingListen else { return }
        guard let recognizer else {
            scheduleRetry()
            return
        }
        if !recognizer.isAvailable {
            tellJS("waiting")
            scheduleRetry()
            return
        }
        startingListen = true
        tearDownRecognition()
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.taskHint = .dictation
        if #available(macOS 13.0, *) {
            request.requiresOnDeviceRecognition = false
            request.contextualStrings = ["Jarvis", "oi Jarvis", "Olá Jarvis", "fala Jarvis", "Ultron", "JARVIS"]
        }
        self.request = request
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0, format.channelCount > 0 else {
            startingListen = false
            logListen("bad format")
            scheduleRetry()
            return
        }
        do {
            input.installTap(onBus: 0, bufferSize: 2048, format: format) { [weak self] buffer, _ in
                request.append(buffer)
                self?.emitLevel(buffer)
            }
            tapInstalled = true
            try engine.start()
        } catch {
            startingListen = false
            logListen("engine \(error)")
            tellJS("error:\(error.localizedDescription)")
            tearDownRecognition()
            scheduleRetry()
            return
        }
        startingListen = false
        logListen("listening sr=\(format.sampleRate) ch=\(format.channelCount)")
        tellJS("listening")
        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }
            if let error {
                let msg = error.localizedDescription
                DispatchQueue.main.async {
                    self.logListen("task \(msg)")
                    if msg.range(of: "speech", options: .caseInsensitive) == nil {
                        self.tellJS("error:\(msg)")
                    }
                }
            }
            if let text = result?.bestTranscription.formattedString, !text.isEmpty {
                let isFinal = result?.isFinal == true
                DispatchQueue.main.async {
                    self.deliverHeard(text, final: isFinal)
                }
            }
            if error != nil || result?.isFinal == true {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                    if self.wantListen { self.beginRecognition() }
                }
            }
        }
    }

    private var lastLevelAt: TimeInterval = 0

    private func emitLevel(_ buffer: AVAudioPCMBuffer) {
        let now = Date().timeIntervalSince1970
        guard now - lastLevelAt > 0.4 else { return }
        lastLevelAt = now
        guard let data = buffer.floatChannelData?[0] else { return }
        let n = Int(buffer.frameLength)
        guard n > 0 else { return }
        var sum: Float = 0
        for i in 0..<n {
            let v = data[i]
            sum += v * v
        }
        let rms = sqrt(sum / Float(n))
        DispatchQueue.main.async { [weak self] in
            self?.tellJS(String(format: "level:%.3f", rms))
        }
    }

    private func tellJS(_ state: String) {
        webView?.evaluateJavaScript(
            "window.__jarvisNativeListen && window.__jarvisNativeListen(\(jsString(state)))",
            completionHandler: nil
        )
    }

    private func jsString(_ raw: String) -> String {
        guard let data = try? JSONSerialization.data(withJSONObject: [raw], options: []),
              let wrapped = String(data: data, encoding: .utf8) else { return "\"\"" }
        return String(wrapped.dropFirst().dropLast())
    }

    private func deliverHeard(_ text: String, final: Bool) {
        lastPartial = text
        lastWasFinal = final
        let flag = final ? "true" : "false"
        webView?.evaluateJavaScript(
            "window.__jarvisNativeHeard && window.__jarvisNativeHeard(\(jsString(text)), \(flag))",
            completionHandler: nil
        )
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
        window.isRestorable = false
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
        config.userContentController.add(self, name: "jarvisRestart")
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
