import AppKit
import AVFoundation
import Darwin
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
        app.activate(ignoringOtherApps: false)
        app.run()
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKUIDelegate, WKNavigationDelegate, WKScriptMessageHandler, AVAudioPlayerDelegate, SFSpeechRecognizerDelegate {
    static var shared: AppDelegate?
    private var window: NSWindow?
    private var webView: WKWebView?
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
    private var paused = false
    private var lastOpenedURL = ""
    private var lastOpenedAt: TimeInterval = 0
    private var idleTimer: Timer?
    private var voiceTimer: Timer?
    private var lastKickAt: TimeInterval = 0
    private let idleHideAfter: TimeInterval = 45
    private let kickCooldown: TimeInterval = 90
    private let fullSize = NSSize(width: 280, height: 380)
    private let orbSize = NSSize(width: 120, height: 120)
    private var compact = false
    private var layouting = false
    private let parkKey = "JarvisParkedOrigin"

    func applicationDidFinishLaunching(_ notification: Notification) {
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
        window.delegate = self
        window.contentView = webView
        self.window = window
        self.webView = webView
        setCompact(true)
        window.orderFrontRegardless()
        webView.load(URLRequest(url: cockpitURL()))
        UserDefaults.standard.set(false, forKey: "NSQuitAlwaysKeepsWindows")
        DispatchQueue.main.async { [weak self] in
            self?.startListen()
            self?.scheduleRecycle()
            self?.resetIdle()
            self?.registerHotKey()
            self?.pokeVoice()
            self?.voiceTimer = Timer.scheduledTimer(withTimeInterval: 20, repeats: true) { [weak self] _ in
                self?.pokeVoice()
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) { [weak self] in
                self?.maybeMorningHello()
            }
        }
    }

    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool { false }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        revealWindow(takeFocus: true)
        return true
    }

    func windowShouldMiniaturize(_ sender: NSWindow) -> Bool {
        setCompact(true)
        return false
    }

    func windowDidDeminiaturize(_ notification: Notification) {
        setCompact(false)
        wantListen = true
        startListen()
    }

    func windowDidMove(_ notification: Notification) {
        savePark()
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
            openExternal(url)
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
            openExternal(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        let body = String(describing: message.body)
        if message.name == "jarvisSpeak" {
            if body == "stop" {
                player?.stop()
                finishSpeak()
            } else {
                speakNative(body)
            }
        } else if message.name == "jarvisListen" {
            if body == "start" {
                startListen()
            } else if body == "restart" {
                restartListen()
            } else if body == "pause" {
                paused = true
            } else if body == "resume" {
                paused = false
                wantListen = true
            } else {
                stopListen()
            }
        } else if message.name == "jarvisRestart" {
            webView?.reloadFromOrigin()
        } else if message.name == "jarvisWindow" {
            if body == "hide" || body == "minimize" {
                hideWindow()
            } else if body == "focus" {
                revealWindow(takeFocus: true)
            } else if body == "show" {
                revealWindow(takeFocus: false)
            } else {
                resetIdle()
            }
        }
    }

    private func resetIdle() {
        idleTimer?.invalidate()
        idleTimer = Timer.scheduledTimer(withTimeInterval: idleHideAfter, repeats: false) { [weak self] _ in
            self?.hideWindow()
        }
    }

    private func hideWindow() {
        setCompact(true)
    }

    private func revealWindow(takeFocus: Bool = false) {
        setCompact(false)
        guard let window else { return }
        if takeFocus {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
        } else {
            window.orderFrontRegardless()
        }
    }

    private func setCompact(_ on: Bool) {
        guard let window else { return }
        if window.isMiniaturized { window.deminiaturize(nil) }
        compact = on
        window.level = .floating
        paintChrome(on)
        layouting = true
        window.setFrame(frameKeepingPlace(on ? orbSize : fullSize), display: true, animate: true)
        layouting = false
        paintChrome(on)
        let flag = on ? "true" : "false"
        webView?.evaluateJavaScript(
            "window.__jarvisSetIdle && window.__jarvisSetIdle(\(flag))",
            completionHandler: nil
        )
        if !on { resetIdle() }
    }

    private func paintChrome(_ compactOn: Bool) {
        guard let window else { return }
        window.isOpaque = false
        window.hasShadow = !compactOn
        window.backgroundColor = .clear
        window.standardWindowButton(.closeButton)?.isHidden = compactOn
        window.standardWindowButton(.miniaturizeButton)?.isHidden = compactOn
        window.standardWindowButton(.zoomButton)?.isHidden = true
        let radius = compactOn ? min(orbSize.width, orbSize.height) / 2 : 18
        if let view = window.contentView {
            view.wantsLayer = true
            view.layer?.cornerRadius = radius
            view.layer?.masksToBounds = true
            view.layer?.backgroundColor = NSColor.clear.cgColor
        }
        webView?.wantsLayer = true
        webView?.layer?.cornerRadius = radius
        webView?.layer?.masksToBounds = true
        if #available(macOS 12.0, *) {
            webView?.underPageBackgroundColor = .clear
        }
    }

    private func pokeVoice() {
        guard let url = URL(string: "http://127.0.0.1:8123/health") else { return }
        var req = URLRequest(url: url)
        req.timeoutInterval = 0.8
        URLSession.shared.dataTask(with: req) { [weak self] _, response, _ in
            let ok = (response as? HTTPURLResponse)?.statusCode == 200
            DispatchQueue.main.async {
                self?.tellJS(ok ? "voice:ok" : "voice:down")
                if !ok { self?.kickVoice() }
            }
        }.resume()
    }

    private func kickVoice() {
        let now = Date().timeIntervalSince1970
        if now - lastKickAt < kickCooldown { return }
        lastKickAt = now
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        task.arguments = ["kickstart", "gui/\(getuid())/ai.theopadilha.jarvis-voice"]
        try? task.run()
    }

    private func registerHotKey() {
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            if self?.isToggleHotKey(event) == true {
                self?.toggleFromHotKey()
                return nil
            }
            return event
        }
        NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            if self?.isToggleHotKey(event) == true {
                self?.toggleFromHotKey()
            }
        }
    }

    private func isToggleHotKey(_ event: NSEvent) -> Bool {
        event.keyCode == 49
            && event.modifierFlags.contains(.option)
            && !event.modifierFlags.contains(.command)
            && !event.modifierFlags.contains(.control)
    }

    private func toggleFromHotKey() {
        if compact { revealWindow(takeFocus: true) }
        else { setCompact(true) }
    }

    private func maybeMorningHello() {
        let now = Date()
        let hour = Calendar.current.component(.hour, from: now)
        guard (5..<12).contains(hour) else { return }
        let stamp = DateFormatter.localizedString(from: now, dateStyle: .short, timeStyle: .none)
        let key = "JarvisLastMorning"
        if UserDefaults.standard.string(forKey: key) == stamp { return }
        UserDefaults.standard.set(stamp, forKey: key)
        speakNative("Bom dia, senhor.")
    }

    private func containsWake(_ text: String) -> Bool {
        text.range(
            of: #"\b(?:jarvis|jarvius|jarbis|javis|jarbas|jarvas|ultron|gerivis|charvis)\b"#,
            options: [.regularExpression, .caseInsensitive]
        ) != nil
    }

    private func openExternal(_ url: URL) {
        let key = url.absoluteString.lowercased()
        let now = Date().timeIntervalSince1970
        if key == lastOpenedURL && now - lastOpenedAt < 8 { return }
        lastOpenedURL = key
        lastOpenedAt = now
        NSWorkspace.shared.open(url)
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
        player?.stop()
        fetchPocketTTS(text) { [weak self] data in
            DispatchQueue.main.async {
                guard let self else { return }
                if let data, self.playAudio(data) { return }
                self.fetchPocketTTS(text) { retry in
                    DispatchQueue.main.async {
                        if let retry, self.playAudio(retry) { return }
                        self.finishSpeak()
                    }
                }
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
        req.timeoutInterval = 4.0
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

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        if wantListen { startListen() }
        if compact {
            webView.evaluateJavaScript(
                "window.__jarvisSetIdle && window.__jarvisSetIdle(true)",
                completionHandler: nil
            )
        }
    }

    func speechRecognizer(_ speechRecognizer: SFSpeechRecognizer, availabilityDidChange available: Bool) {
        logListen("available \(available)")
        guard available, wantListen, !useModern else { return }
        if engine.isRunning, task != nil { return }
        scheduleRetry()
    }

    private func finishSpeak() {
        paused = false
        webView?.evaluateJavaScript("window.__jarvisOnSpeakDone && window.__jarvisOnSpeakDone()", completionHandler: nil)
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
            if self?.paused == true { return }
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
        if containsWake(text) {
            if player?.isPlaying == true {
                player?.stop()
                finishSpeak()
            }
        }
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
        let size = fullSize
        let rect = frameKeepingPlace(size)
        let window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable, .fullSizeContentView],
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
        window.isMovable = true
        window.isOpaque = false
        window.backgroundColor = .clear
        window.standardWindowButton(.miniaturizeButton)?.isHidden = false
        window.standardWindowButton(.zoomButton)?.isHidden = true
        return window
    }

    private func makeWebView() -> WKWebView {
        let config = WKWebViewConfiguration()
        config.mediaTypesRequiringUserActionForPlayback = []
        config.websiteDataStore = .default()
        config.userContentController.add(self, name: "jarvisSpeak")
        config.userContentController.add(self, name: "jarvisListen")
        config.userContentController.add(self, name: "jarvisRestart")
        config.userContentController.add(self, name: "jarvisWindow")
        if #available(macOS 11.0, *) {
            config.defaultWebpagePreferences.allowsContentJavaScript = true
        }
        let view = WKWebView(frame: .zero, configuration: config)
        view.uiDelegate = self
        view.navigationDelegate = self
        view.allowsBackForwardNavigationGestures = false
        view.setValue(false, forKey: "drawsBackground")
        if #available(macOS 12.0, *) {
            view.underPageBackgroundColor = .clear
        }
        return view
    }

    private func savePark() {
        guard !layouting, let window else { return }
        let origin = window.frame.origin
        UserDefaults.standard.set("\(origin.x),\(origin.y)", forKey: parkKey)
    }

    private func parkedOrigin() -> NSPoint? {
        let parts = (UserDefaults.standard.string(forKey: parkKey) ?? "").split(separator: ",")
        guard parts.count == 2, let x = Double(parts[0]), let y = Double(parts[1]) else { return nil }
        return NSPoint(x: x, y: y)
    }

    private func frameKeepingPlace(_ size: NSSize) -> NSRect {
        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        var origin: NSPoint
        if let window {
            let current = window.frame
            origin = NSPoint(x: current.midX - size.width / 2, y: current.midY - size.height / 2)
        } else if let saved = parkedOrigin() {
            origin = saved
        } else {
            origin = NSPoint(x: screen.maxX - size.width - 16, y: screen.minY + 24)
        }
        var rect = NSRect(origin: origin, size: size)
        if rect.maxX > screen.maxX { rect.origin.x = screen.maxX - size.width }
        if rect.maxY > screen.maxY { rect.origin.y = screen.maxY - size.height }
        if rect.minX < screen.minX { rect.origin.x = screen.minX }
        if rect.minY < screen.minY { rect.origin.y = screen.minY }
        return rect
    }
}
