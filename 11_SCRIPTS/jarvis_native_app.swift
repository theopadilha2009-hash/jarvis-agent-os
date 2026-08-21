import AppKit
import AVFoundation
import CoreGraphics
import Darwin
import ScreenCaptureKit
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

final class OverlayWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

final class OverlayWebView: WKWebView {
    override var isOpaque: Bool { false }

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override var mouseDownCanMoveWindow: Bool { false }
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
    private var voiceMisses = 0
    private var speakingNow = false
    private let idleHideAfter: TimeInterval = 12
    private let kickCooldown: TimeInterval = 90
    private let fullSize = NSSize(width: 268, height: 408)
    private let orbSize = NSSize(width: 72, height: 72)
    private var compact = false
    private var wakeOnly = true
    private var layouting = false
    private var dragTracking: (origin: NSPoint, mouse: NSPoint)?
    private var dragMoved = false
    private var localDragMonitor: Any?
    private var globalDragMonitor: Any?
    private let parkKey = "JarvisParkedOrigin"
    private let tokenKey = "JarvisOwnerToken"

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
        let paired = !(UserDefaults.standard.string(forKey: tokenKey) ?? "").isEmpty
        setCompact(paired)
        installDrag()
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
            } else if body == "arm" {
                wakeOnly = false
                paused = false
                wantListen = true
                startListen()
            } else if body == "sleep" {
                wakeOnly = true
            } else {
                stopListen()
            }
        } else if message.name == "jarvisRestart" {
            restartFromOrigin()
        } else if message.name == "jarvisWindow" {
            if body == "hide" || body == "minimize" {
                hideWindow()
            } else if body == "focus" {
                revealWindow(takeFocus: true)
            } else if body == "show" {
                revealWindow(takeFocus: false)
            } else if body.hasPrefix("token:") {
                saveToken(String(body.dropFirst(6)))
            } else {
                resetIdle()
            }
        } else if message.name == "jarvisSee" {
            captureScreen { [weak self] payload in
                self?.webView?.evaluateJavaScript(
                    "window.__jarvisOnScreen && window.__jarvisOnScreen(\(self?.jsString(payload) ?? "\"empty\""))",
                    completionHandler: nil
                )
            }
        }
    }

    private func resetIdle() {
        idleTimer?.invalidate()
        if (UserDefaults.standard.string(forKey: tokenKey) ?? "").isEmpty { return }
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
        window.isMovable = true
        window.isMovableByWindowBackground = false
        let card = NSColor(srgbRed: 0.07, green: 0.047, blue: 0.11, alpha: 1)
        window.backgroundColor = compactOn ? .clear : card
        window.standardWindowButton(.closeButton)?.isHidden = true
        window.standardWindowButton(.miniaturizeButton)?.isHidden = true
        window.standardWindowButton(.zoomButton)?.isHidden = true
        let radius = compactOn ? min(orbSize.width, orbSize.height) / 2 : 18
        if let view = window.contentView {
            view.wantsLayer = true
            view.layer?.cornerRadius = radius
            view.layer?.masksToBounds = true
            view.layer?.backgroundColor = compactOn ? NSColor.clear.cgColor : card.cgColor
        }
        webView?.wantsLayer = true
        webView?.layer?.cornerRadius = radius
        webView?.layer?.masksToBounds = true
        if #available(macOS 12.0, *) {
            webView?.underPageBackgroundColor = compactOn ? .clear : NSColor(srgbRed: 0.07, green: 0.047, blue: 0.11, alpha: 1)
        }
    }

    private func pokeVoice() {
        if speakingNow { return }
        guard let url = URL(string: "http://127.0.0.1:8123/health") else { return }
        var req = URLRequest(url: url)
        req.timeoutInterval = 2.0
        URLSession.shared.dataTask(with: req) { [weak self] _, response, error in
            let ok = (response as? HTTPURLResponse)?.statusCode == 200
            let code = (error as? URLError)?.code
            let dead = !ok && (code == .cannotConnectToHost || code == .cannotFindHost)
            DispatchQueue.main.async {
                guard let self else { return }
                if ok {
                    self.voiceMisses = 0
                    self.tellJS("voice:ok")
                    return
                }
                if self.speakingNow { return }
                if dead {
                    self.voiceMisses += 1
                    if self.voiceMisses >= 3 {
                        self.tellJS("voice:down")
                        self.kickVoice()
                    }
                }
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
        speakingNow = true
        player?.stop()
        fetchPocketTTS(text) { [weak self] data in
            DispatchQueue.main.async {
                guard let self else { return }
                if let data, self.playAudio(data) {
                    self.voiceMisses = 0
                    self.tellJS("voice:ok")
                    return
                }
                self.fetchPocketTTS(text) { retry in
                    DispatchQueue.main.async {
                        if let retry, self.playAudio(retry) {
                            self.voiceMisses = 0
                            self.tellJS("voice:ok")
                            return
                        }
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
        req.timeoutInterval = 15.0
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
        if let token = UserDefaults.standard.string(forKey: tokenKey), !token.isEmpty {
            webView.evaluateJavaScript(
                "try{localStorage.setItem('jarvis-owner-token-v1',\(jsString(token)));}catch(e){}",
                completionHandler: nil
            )
        }
        let flag = compact ? "true" : "false"
        webView.evaluateJavaScript(
            "window.__jarvisSetIdle && window.__jarvisSetIdle(\(flag))",
            completionHandler: nil
        )
    }

    func speechRecognizer(_ speechRecognizer: SFSpeechRecognizer, availabilityDidChange available: Bool) {
        logListen("available \(available)")
        guard available, wantListen, !useModern else { return }
        if engine.isRunning, task != nil { return }
        scheduleRetry()
    }

    private func finishSpeak() {
        speakingNow = false
        paused = false
        webView?.evaluateJavaScript("window.__jarvisOnSpeakDone && window.__jarvisOnSpeakDone()", completionHandler: nil)
        resetIdle()
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
        if wakeOnly || compact { return }
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

    private func captureScreen(done: @escaping (String) -> Void) {
        if #available(macOS 10.15, *), !CGPreflightScreenCaptureAccess() {
            CGRequestScreenCaptureAccess()
            done("denied")
            return
        }
        if #available(macOS 14.0, *) {
            captureModern(done)
            return
        }
        captureLegacy(done)
    }

    @available(macOS 14.0, *)
    private func captureModern(_ done: @escaping (String) -> Void) {
        Task { [weak self] in
            guard let self else { return }
            do {
                let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
                guard let window = self.window else {
                    self.finishCapture("empty", done)
                    return
                }
                let screen = window.screen ?? NSScreen.main
                let number = screen.flatMap { $0.deviceDescription[NSDeviceDescriptionKey(rawValue: "NSScreenNumber")] as? NSNumber }
                let displayID = number.map { CGDirectDisplayID($0.uint32Value) }
                let display = content.displays.first(where: { displayID != nil && $0.displayID == displayID }) ?? content.displays.first
                guard let display else {
                    self.finishCapture("empty", done)
                    return
                }
                let excluded = content.windows.filter { $0.owningApplication?.bundleIdentifier == bundleID }
                let filter = SCContentFilter(display: display, excludingWindows: excluded)
                let config = SCStreamConfiguration()
                let maxW = 1280
                config.width = min(maxW, display.width)
                config.height = max(1, Int(Double(display.height) * (Double(config.width) / max(Double(display.width), 1))))
                config.showsCursor = true
                let image = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: config)
                guard let data = self.jpegData(from: image), data.count > 1200 else {
                    self.finishCapture("empty", done)
                    return
                }
                self.finishCapture("data:image/jpeg;base64," + data.base64EncodedString(), done)
            } catch {
                self.finishCapture("denied", done)
            }
        }
    }

    private func captureLegacy(_ done: @escaping (String) -> Void) {
        guard let window else {
            done("empty")
            return
        }
        let screen = window.screen ?? NSScreen.main
        let index = ((screen.flatMap { NSScreen.screens.firstIndex(of: $0) }) ?? 0) + 1
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("jarvis-see.jpg")
        let keepCompact = compact
        window.alphaValue = 0
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.12) { [weak self] in
            guard let self else { return }
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
            task.arguments = ["-x", "-t", "jpg", "-D", "\(index)", url.path]
            do {
                try task.run()
                task.waitUntilExit()
            } catch {
                window.alphaValue = 1
                self.paintChrome(keepCompact)
                done("empty")
                return
            }
            window.alphaValue = 1
            self.paintChrome(keepCompact)
            guard task.terminationStatus == 0,
                  let data = try? Data(contentsOf: url),
                  data.count > 1200
            else {
                done("empty")
                return
            }
            try? FileManager.default.removeItem(at: url)
            done("data:image/jpeg;base64," + data.base64EncodedString())
        }
    }

    private func finishCapture(_ payload: String, _ done: @escaping (String) -> Void) {
        DispatchQueue.main.async { done(payload) }
    }

    private func jpegData(from image: CGImage) -> Data? {
        let maxW: CGFloat = 1280
        let srcW = CGFloat(image.width)
        let srcH = CGFloat(image.height)
        let scale = min(1, maxW / max(srcW, 1))
        let outW = max(1, Int((srcW * scale).rounded()))
        let outH = max(1, Int((srcH * scale).rounded()))
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        guard let ctx = CGContext(
            data: nil,
            width: outW,
            height: outH,
            bitsPerComponent: 8,
            bytesPerRow: 0,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else { return nil }
        ctx.interpolationQuality = .medium
        ctx.draw(image, in: CGRect(x: 0, y: 0, width: outW, height: outH))
        guard let scaled = ctx.makeImage() else { return nil }
        let rep = NSBitmapImageRep(cgImage: scaled)
        return rep.representation(using: .jpeg, properties: [.compressionFactor: 0.52])
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
            wakeOnly = false
            if compact { revealWindow(takeFocus: false) }
            if player?.isPlaying == true {
                player?.stop()
                finishSpeak()
            }
        } else if wakeOnly {
            return
        }
        let flag = final ? "true" : "false"
        webView?.evaluateJavaScript(
            "window.__jarvisNativeHeard && window.__jarvisNativeHeard(\(jsString(text)), \(flag))",
            completionHandler: nil
        )
    }

    private func restartFromOrigin() {
        let types: Set<String> = [WKWebsiteDataTypeDiskCache, WKWebsiteDataTypeMemoryCache]
        webView?.configuration.websiteDataStore.removeData(ofTypes: types, modifiedSince: .distantPast) { [weak self] in
            DispatchQueue.main.async {
                guard let self else { return }
                var comps = URLComponents(url: self.cockpitURL(), resolvingAgainstBaseURL: false)
                var items = (comps?.queryItems ?? []).filter { $0.name != "r" }
                items.append(URLQueryItem(name: "r", value: String(Int(Date().timeIntervalSince1970))))
                comps?.queryItems = items
                guard let url = comps?.url else {
                    self.webView?.reloadFromOrigin()
                    return
                }
                let req = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
                self.webView?.load(req)
            }
        }
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
        let window = OverlayWindow(
            contentRect: rect,
            styleMask: [.borderless, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "JARVIS"
        window.isRestorable = false
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.isMovable = true
        window.isMovableByWindowBackground = false
        window.level = .floating
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        window.setFrameAutosaveName("")
        window.setFrame(rect, display: true)
        window.isOpaque = false
        window.hasShadow = false
        window.backgroundColor = .clear
        window.acceptsMouseMovedEvents = true
        window.ignoresMouseEvents = false
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
        config.userContentController.add(self, name: "jarvisSee")
        if let token = UserDefaults.standard.string(forKey: tokenKey), !token.isEmpty {
            let source = "try{localStorage.setItem('jarvis-owner-token-v1',\(jsString(token)));}catch(e){}"
            config.userContentController.addUserScript(
                WKUserScript(source: source, injectionTime: .atDocumentStart, forMainFrameOnly: true)
            )
        }
        if #available(macOS 11.0, *) {
            config.defaultWebpagePreferences.allowsContentJavaScript = true
        }
        let view = OverlayWebView(frame: .zero, configuration: config)
        view.uiDelegate = self
        view.navigationDelegate = self
        view.autoresizingMask = [.width, .height]
        view.allowsBackForwardNavigationGestures = false
        view.setValue(false, forKey: "drawsBackground")
        if #available(macOS 12.0, *) {
            view.underPageBackgroundColor = .clear
        }
        return view
    }

    private func installDrag() {
        localDragMonitor = NSEvent.addLocalMonitorForEvents(
            matching: [.leftMouseDown, .leftMouseDragged, .leftMouseUp]
        ) { [weak self] event in
            self?.handleWindowDrag(event, consume: true) ?? event
        }
        globalDragMonitor = NSEvent.addGlobalMonitorForEvents(
            matching: [.leftMouseDragged, .leftMouseUp]
        ) { [weak self] event in
            guard let self, self.dragTracking != nil else { return }
            _ = self.handleWindowDrag(event, consume: false)
        }
    }

    private func dragAllowed(for event: NSEvent) -> Bool {
        guard let window else { return false }
        if compact { return true }
        return event.locationInWindow.y > 96
    }

    private func handleWindowDrag(_ event: NSEvent, consume: Bool) -> NSEvent? {
        guard let window else { return event }
        let ours = event.window == window
            || event.windowNumber == window.windowNumber
            || dragTracking != nil
        if !ours { return event }
        switch event.type {
        case .leftMouseDown:
            guard dragAllowed(for: event) else {
                dragTracking = nil
                dragMoved = false
                return event
            }
            dragTracking = (window.frame.origin, NSEvent.mouseLocation)
            dragMoved = false
            resetIdle()
            return event
        case .leftMouseDragged:
            guard let track = dragTracking else { return event }
            let mouse = NSEvent.mouseLocation
            let dx = mouse.x - track.mouse.x
            let dy = mouse.y - track.mouse.y
            if !dragMoved && abs(dx) < 4 && abs(dy) < 4 { return event }
            dragMoved = true
            layouting = true
            window.setFrameOrigin(NSPoint(x: track.origin.x + dx, y: track.origin.y + dy))
            layouting = false
            return consume ? nil : event
        case .leftMouseUp:
            let moved = dragMoved
            dragTracking = nil
            dragMoved = false
            if moved {
                savePark()
                resetIdle()
                return consume ? nil : event
            }
            return event
        default:
            return event
        }
    }

    private func saveToken(_ token: String) {
        let clipped = String(token.prefix(2000))
        if clipped.isEmpty {
            UserDefaults.standard.removeObject(forKey: tokenKey)
        } else {
            UserDefaults.standard.set(clipped, forKey: tokenKey)
        }
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

    private func activeScreenFrame() -> NSRect {
        if let window {
            if let screen = window.screen { return screen.visibleFrame }
            let frame = window.frame
            if let screen = NSScreen.screens.first(where: { NSIntersectionRect($0.frame, frame).width > 8 }) {
                return screen.visibleFrame
            }
        }
        return NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
    }

    private func frameKeepingPlace(_ size: NSSize) -> NSRect {
        let screen = activeScreenFrame()
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
