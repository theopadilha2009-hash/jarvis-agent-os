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

// Padrão Handy: overlay é NSPanel com .nonactivatingPanel — recebe clique e
// digitação sem ativar o app nem roubar o foco do que estava em uso. O roubo
// de foco explícito fica isolado em revealWindow(takeFocus: true).
final class OverlayWindow: NSPanel {
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
    private var speechChunks: [String] = []
    private var speechAudio: [Data] = []
    private var speechFetchInFlight = false
    private var speechWaiting = false
    private var speechVoiceOKSent = false
    private var speechHeadRetried = false
    private var speechGeneration = 0
    private var webViewReady = false
    private var voiceReady = false
    private var greeted = false
    // 12s escondia a janela no meio do uso (logo depois do login, do login).
    // 60s dá tempo de ler a resposta; falar com o JARVIS reseta o timer.
    private let idleHideAfter: TimeInterval = 60
    private let kickCooldown: TimeInterval = 90
    private let fullSize = NSSize(width: 268, height: 380)
    private let zoomSize = NSSize(width: 320, height: 560)
    private var isZoomed = false
    private let orbSize = NSSize(width: 72, height: 72)
    private let replySize = NSSize(width: 220, height: 84)
    private var replyChip = ""
    private var compact = false
    private var wakeOnly = true
    private var layouting = false
    private var dragTracking: (origin: NSPoint, mouse: NSPoint)?
    private var dragMoved = false
    private var localDragMonitor: Any?
    private var globalDragMonitor: Any?
    private let parkKey = "JarvisParkedOrigin"
    private let tokenKey = "JarvisOwnerToken"
    // Padrão Handy: Secure Input de outro app bloqueia atalhos globais e o
    // teclado seguro; sem monitor, o JARVIS falha em silêncio. O estado vai
    // para o cockpit pelo tellJS só quando muda (sem spam a cada poll).
    private var secureInputTimer: Timer?
    private var secureInputActive = false
    private var secureInputApp = ""

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
        // Revalida sempre: o HTML carrega o ?v= dos assets e, cacheado como
        // immutable, prendia o app numa versão antiga para sempre.
        webView.load(URLRequest(url: cockpitURL(), cachePolicy: .reloadRevalidatingCacheData, timeoutInterval: 20))
        UserDefaults.standard.set(false, forKey: "NSQuitAlwaysKeepsWindows")
        DispatchQueue.main.async { [weak self] in
            self?.startListen()
            self?.scheduleRecycle()
            self?.resetIdle()
            self?.registerHotKey()
            self?.startSecureInputMonitor()
            self?.pokeVoice()
            self?.voiceTimer = Timer.scheduledTimer(withTimeInterval: 20, repeats: true) { [weak self] _ in
                self?.pokeVoice()
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
            } else if body == "shutdown" || body == "quit" || body == "close" || body == "exit" {
                NSApplication.shared.terminate(nil)
            } else if body == "zoom" || body == "toggleSize" || body == "maximize" {
                toggleZoom()
            } else if body == "fullscreen" {
                toggleFullscreen()
            } else if body == "focus" {
                revealWindow(takeFocus: true)
            } else if body == "show" {
                revealWindow(takeFocus: false)
            } else if body.hasPrefix("reply:") {
                holdReply(String(body.dropFirst(6)))
            } else if body.hasPrefix("token:") {
                saveToken(String(body.dropFirst(6)))
            } else {
                resetIdle()
            }
        } else if message.name == "jarvisAction" {
            let cmd = String(describing: message.body)
            let script = self.actionsScriptPath()
            DispatchQueue.global(qos: .userInitiated).async { [weak self] in
                let proc = Process()
                proc.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
                proc.arguments = [
                    script,
                    cmd
                ]
                let pipe = Pipe()
                proc.standardOutput = pipe
                try? proc.run()
                proc.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                if let output = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
                   !output.isEmpty,
                   !output.contains("Comando não reconhecido") {
                    DispatchQueue.main.async {
                        self?.speakNative(output)
                        self?.webView?.evaluateJavaScript(
                            "window.__jarvisOnActionResult && window.__jarvisOnActionResult(\(self?.jsString(output) ?? "\"\""))",
                            completionHandler: nil
                        )
                    }
                }
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
            guard let self else { return }
            if self.speakingNow {
                self.resetIdle()
                return
            }
            self.hideWindow()
        }
    }

    private func holdReply(_ raw: String) {
        var text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.count > 48 {
            text = String(text.prefix(45)) + "…"
        }
        replyChip = text
        if compact { setCompact(true) }
    }

    private func compactFrameSize() -> NSSize {
        replyChip.isEmpty ? orbSize : replySize
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

    private func toggleZoom() {
        guard let window, !compact else { return }
        isZoomed.toggle()
        let target = isZoomed ? zoomSize : fullSize
        layouting = true
        window.setFrame(frameKeepingPlace(target), display: true, animate: true)
        layouting = false
    }

    // A janela é borderless, então toggleFullScreen do NSWindow não tem botão
    // nem efeito garantido: cobrir o frame da tela é o "tela cheia" real.
    // Se ela já cobre (ou está no fullscreen do sistema), volta ao tamanho
    // normal; se entrou no fullscreen do sistema, sai pelo toggle nativo.
    private func toggleFullscreen() {
        guard let window else { return }
        if compact { setCompact(false) }
        if window.styleMask.contains(.fullScreen) {
            window.toggleFullScreen(nil)
            return
        }
        guard let screen = window.screen ?? NSScreen.main else { return }
        let target = NSRect(origin: screen.frame.origin, size: screen.frame.size)
        let covering = abs(window.frame.width - target.width) < 2
            && abs(window.frame.height - target.height) < 2
        layouting = true
        window.setFrame(covering ? frameKeepingPlace(fullSize) : target, display: true, animate: true)
        layouting = false
        savePark()
    }

    private func actionsScriptPath() -> String {
        let candidates = [
            "/Users/usuario1/Projetos pessoais/jarvis/11_SCRIPTS/jarvis_actions.py",
            "/Users/usuario1/orca/workspaces/Terminal/ultron-opus-redo/11_SCRIPTS/jarvis_actions.py"
        ]
        for path in candidates where FileManager.default.fileExists(atPath: path) {
            return path
        }
        return "/Users/usuario1/Projetos pessoais/jarvis/11_SCRIPTS/jarvis_actions.py"
    }

    private func setCompact(_ on: Bool) {
        guard let window else { return }
        if window.isMiniaturized { window.deminiaturize(nil) }
        compact = on
        if on { isZoomed = false }
        window.level = .floating
        paintChrome(on)
        layouting = true
        let targetSize = on ? compactFrameSize() : (isZoomed ? zoomSize : fullSize)
        window.setFrame(frameKeepingPlace(targetSize), display: true, animate: true)
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
        let chip = compactOn && !replyChip.isEmpty
        window.hasShadow = !compactOn || chip
        window.isMovable = true
        window.isMovableByWindowBackground = false
        let card = NSColor(srgbRed: 0.07, green: 0.047, blue: 0.11, alpha: 1)
        window.backgroundColor = compactOn && !chip ? .clear : card
        window.standardWindowButton(.closeButton)?.isHidden = true
        window.standardWindowButton(.miniaturizeButton)?.isHidden = true
        window.standardWindowButton(.zoomButton)?.isHidden = true
        let radius: CGFloat = compactOn ? (chip ? 22 : min(orbSize.width, orbSize.height) / 2) : 18
        if let view = window.contentView {
            view.wantsLayer = true
            view.layer?.cornerRadius = radius
            view.layer?.masksToBounds = true
            view.layer?.backgroundColor = compactOn && !chip ? NSColor.clear.cgColor : card.cgColor
        }
        webView?.wantsLayer = true
        webView?.layer?.cornerRadius = radius
        webView?.layer?.masksToBounds = true
        if #available(macOS 12.0, *) {
            webView?.underPageBackgroundColor = compactOn && !chip ? .clear : NSColor(srgbRed: 0.07, green: 0.047, blue: 0.11, alpha: 1)
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
                    self.voiceReady = true
                    self.checkAllReadyAndGreet()
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

    private func startSecureInputMonitor() {
        secureInputTimer?.invalidate()
        secureInputTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            self?.pollSecureInput()
        }
    }

    private func pollSecureInput() {
        let session = CGSessionCopyCurrentDictionary() as NSDictionary?
        var pid: Int32 = 0
        if let raw = session?["kCGSSessionSecureInputPID"] {
            if let num = raw as? NSNumber {
                pid = num.int32Value
            } else if let text = raw as? String, let parsed = Int32(text) {
                pid = parsed
            }
        }
        guard pid > 0 else {
            notifySecureInput(active: false, app: "")
            return
        }
        let name = NSRunningApplication(processIdentifier: pid)?.localizedName ?? "um aplicativo"
        notifySecureInput(active: true, app: name)
    }

    private func notifySecureInput(active: Bool, app: String) {
        let changed = active != secureInputActive || (active && app != secureInputApp)
        guard changed else { return }
        secureInputActive = active
        secureInputApp = app
        if active {
            tellJS("secureinput:Atalhos globais bloqueados — \(app) está segurando Secure Input")
        } else {
            tellJS("secureinput:off")
        }
        logListen("secureinput \(active ? app : "off")")
    }

    
    private func checkAllReadyAndGreet() {
        guard webViewReady && voiceReady && !greeted else { return }
        greeted = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
            self?.maybeMorningHello()
        }
    }
    private func maybeMorningHello() {
        // Opt-in: o dono reclamou de o JARVIS falar sozinho ao abrir. Fala só
        // se `defaults write` habilitar, e sempre espelha o texto na UI.
        guard UserDefaults.standard.bool(forKey: "JarvisMorningHelloEnabled") else { return }
        let now = Date()
        let hour = Calendar.current.component(.hour, from: now)
        guard (5..<12).contains(hour) else { return }
        let stamp = DateFormatter.localizedString(from: now, dateStyle: .short, timeStyle: .none)
        let key = "JarvisLastMorning"
        if UserDefaults.standard.string(forKey: key) == stamp { return }
        UserDefaults.standard.set(stamp, forKey: key)
        webView?.evaluateJavaScript(
            "window.__jarvisOnActionResult && window.__jarvisOnActionResult('Bom dia, senhor.')",
            completionHandler: nil
        )
        speakNative("Bom dia, senhor.")
    }

    private func containsWake(_ text: String) -> Bool {
        // "jarbas" é nome de pessoa; "ultron" aparece em conversa tech.
        // As duas causavam disparo falso da escuta contínua.
        text.range(
            of: #"\b(?:jarvis|jarvius|jarbis|javis)\b"#,
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
        guard player === self.player else { return }
        playNextSpeechChunk()
    }

    private func speakNative(_ raw: String) {
        let text = String(raw.prefix(220)).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else {
            finishSpeak()
            return
        }
        speechGeneration += 1
        speakingNow = true
        player?.stop()
        speechChunks = speechSentences(text)
        speechAudio = []
        speechFetchInFlight = false
        speechWaiting = true
        speechVoiceOKSent = false
        speechHeadRetried = false
        pumpSpeech()
    }

    // Frases por . ! ? … e quebra de linha; frase <8 chars gruda na seguinte.
    // Texto sem separador vira frase única — caminho comum, igual ao comportamento antigo.
    private func speechSentences(_ text: String) -> [String] {
        var parts: [String] = []
        var current = ""
        for ch in text {
            if ch == "." || ch == "!" || ch == "?" || ch == "…" {
                current.append(ch)
                pushSentence(&parts, &current)
            } else if ch == "\n" || ch == "\r" {
                pushSentence(&parts, &current)
            } else {
                current.append(ch)
            }
        }
        pushSentence(&parts, &current)
        guard parts.count > 1 else { return parts }
        var merged: [String] = []
        var index = 0
        while index < parts.count {
            var piece = parts[index]
            while piece.count < 8, index + 1 < parts.count {
                index += 1
                piece += " " + parts[index]
            }
            merged.append(piece)
            index += 1
        }
        return merged
    }

    private func pushSentence(_ parts: inout [String], _ current: inout String) {
        let piece = current.trimmingCharacters(in: .whitespacesAndNewlines)
        if !piece.isEmpty { parts.append(piece) }
        current = ""
    }

    // Um fetch por vez: o próximo sai quando o anterior termina ou quando o
    // chunk atual começa a tocar. Fila toda abortada pelo finishSpeak.
    private func pumpSpeech() {
        guard !speechFetchInFlight, let chunk = speechChunks.first else { return }
        speechChunks.removeFirst()
        speechFetchInFlight = true
        let generation = speechGeneration
        let isHead = !speechVoiceOKSent && speechAudio.isEmpty && !speechHeadRetried
        fetchPocketTTS(chunk) { [weak self] data in
            DispatchQueue.main.async {
                guard let self, self.speechGeneration == generation else { return }
                self.speechFetchInFlight = false
                if let data {
                    self.speechAudio.append(data)
                } else if isHead {
                    // Frase 1: um retry, como no caminho antigo; resto da fila pula a frase.
                    self.speechHeadRetried = true
                    self.speechChunks.insert(chunk, at: 0)
                }
                self.pumpSpeech()
                if self.speechWaiting {
                    self.playNextSpeechChunk()
                }
            }
        }
    }

    private func playNextSpeechChunk() {
        if let data = speechAudio.first {
            speechAudio.removeFirst()
            speechWaiting = false
            if playAudio(data) {
                if !speechVoiceOKSent {
                    speechVoiceOKSent = true
                    voiceMisses = 0
                    tellJS("voice:ok")
                }
                pumpSpeech()
            } else {
                playNextSpeechChunk()
            }
            return
        }
        if speechFetchInFlight || !speechChunks.isEmpty {
            speechWaiting = true
        } else {
            finishSpeak()
        }
    }

    private func fetchPocketTTS(_ text: String, done: @escaping (Data?) -> Void) {
        guard let url = URL(string: "http://127.0.0.1:8123/speech") else {
            done(nil)
            return
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.timeoutInterval = 8.0
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
        webViewReady = true
        checkAllReadyAndGreet()
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
        speechGeneration += 1
        speechChunks = []
        speechAudio = []
        speechFetchInFlight = false
        speechWaiting = false
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
        // Bias mínimo: frases como "oi Jarvis" ensinavam o reconhecedor a
        // alucinar o wake em ruído, disparando fala sozinha.
        context.contextualStrings = [.general: ["Jarvis"]]
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
        hadVoiceInCycle = false
        silenceStartedAt = 0
        input.installTap(onBus: 0, bufferSize: 4096, format: micFormat) { [weak self] buffer, _ in
            if self?.paused == true { return }
            self?.observeSilence(buffer)
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
            request.contextualStrings = ["Jarvis", "JARVIS"]
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
            hadVoiceInCycle = false
            silenceStartedAt = 0
            input.installTap(onBus: 0, bufferSize: 2048, format: format) { [weak self] buffer, _ in
                request.append(buffer)
                self?.observeSilence(buffer)
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

    // Padrão Handy: auto-stop por silêncio. Depois de voz detectada (RMS acima
    // do piso), 1.8s contínuos abaixo do piso fecham a captura corrente — o
    // parcial pendente é entregue como final e o ciclo recomeça pelos caminhos
    // que já existiam (clássico reinicia no recognitionTask; moderno reinicia
    // o pipeline pelo mesmo caminho do restart do JS). Sem voz nova, nada
    // acontece: a escuta contínua por wake word segue intacta.
    private let silenceRmsFloor: Float = 0.008
    private let silenceStopAfter: TimeInterval = 1.8
    private var hadVoiceInCycle = false
    private var silenceStartedAt: TimeInterval = 0
    private var silenceRestarting = false

    private func bufferRMS(_ buffer: AVAudioPCMBuffer) -> Float {
        guard let data = buffer.floatChannelData?[0] else { return 0 }
        let n = Int(buffer.frameLength)
        guard n > 0 else { return 0 }
        var sum: Float = 0
        for i in 0..<n {
            let v = data[i]
            sum += v * v
        }
        return sqrt(sum / Float(n))
    }

    private func observeSilence(_ buffer: AVAudioPCMBuffer) {
        if bufferRMS(buffer) >= silenceRmsFloor {
            hadVoiceInCycle = true
            silenceStartedAt = 0
            return
        }
        guard hadVoiceInCycle, !silenceRestarting else { return }
        let now = Date().timeIntervalSince1970
        if silenceStartedAt == 0 { silenceStartedAt = now }
        guard now - silenceStartedAt >= silenceStopAfter else { return }
        silenceStartedAt = 0
        hadVoiceInCycle = false
        endCaptureOnSilence()
    }

    private func endCaptureOnSilence() {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.logListen("silence stop")
            if self.useModern {
                self.finalizeModernOnSilence()
            } else {
                // Clássico: endAudio flusha o parcial; o próprio
                // recognitionTask já reabre o ciclo em beginRecognition.
                self.request?.endAudio()
            }
        }
    }

    private func finalizeModernOnSilence() {
        guard wantListen, !silenceRestarting else { return }
        silenceRestarting = true
        // Fecha o stream: o transcriber finaliza o pendente e o tearDown
        // entrega o parcial remanescente como final antes de recomeçar.
        analyzerFinish?()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { [weak self] in
            guard let self else { return }
            silenceRestarting = false
            guard wantListen else { return }
            stopModern()
            tearDownRecognition()
            startListen()
        }
    }

    private func emitLevel(_ buffer: AVAudioPCMBuffer) {
        if wakeOnly || compact { return }
        let now = Date().timeIntervalSince1970
        guard now - lastLevelAt > 0.4 else { return }
        lastLevelAt = now
        let rms = bufferRMS(buffer)
        guard rms > 0 else { return }
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
        let clean = text.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: .current).lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        if clean.contains("vai dormir") || clean.contains("va dormir") || clean.contains("desliga jarvis") || clean.contains("desligar jarvis") || clean.contains("desligar o jarvis") || clean.contains("fechar jarvis") || clean.contains("fecha o jarvis") || clean.contains("desligar completamente") || clean == "desligar" || clean == "fechar" {
            if final {
                speakNative("Até logo, senhor. Desligando.")
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.8) {
                    NSApp.terminate(nil)
                }
            }
            return
        }
        if clean.contains("antigravity") && (clean.contains("projeto") || clean.contains("abre") || clean.contains("abrir") || clean.contains("pasta")) {
            if final {
                handleOpenAntigravity(speech: text)
            }
            return
        }
        if final {
            let script = self.actionsScriptPath()
            DispatchQueue.global(qos: .userInitiated).async { [weak self] in
                let proc = Process()
                proc.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
                proc.arguments = [
                    script,
                    text
                ]
                let pipe = Pipe()
                proc.standardOutput = pipe
                try? proc.run()
                proc.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                if let output = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
                   !output.isEmpty,
                   !output.contains("Comando não reconhecido") {
                    DispatchQueue.main.async {
                        self?.speakNative(output)
                    }
                }
            }
        }
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

    
    private func handleOpenAntigravity(speech: String) {
        let lower = speech.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: .current).lowercased()
        var target = ""
        if let r = lower.range(of: "projeto") {
            target = String(lower[r.upperBound...])
        } else if let r = lower.range(of: "antigravity") {
            target = String(lower[r.upperBound...])
        }
        target = target.replacingOccurrences(of: "da", with: "")
            .replacingOccurrences(of: "do", with: "")
            .replacingOccurrences(of: "de", with: "")
            .replacingOccurrences(of: "no", with: "")
            .replacingOccurrences(of: "na", with: "")
            .replacingOccurrences(of: "em", with: "")
            .replacingOccurrences(of: "antigravity", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let query = target.replacingOccurrences(of: " ", with: "")
        let searchDirs = [
            "/Users/usuario1/Projetos pessoais",
            "/Users/usuario1/VAMOOAIPROD",
            "/Users/usuario1"
        ]
        let fm = FileManager.default
        var foundPath: String?
        for dir in searchDirs {
            guard let items = try? fm.contentsOfDirectory(atPath: dir) else { continue }
            for item in items {
                let norm = item.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: .current)
                    .lowercased()
                    .replacingOccurrences(of: "_", with: "")
                    .replacingOccurrences(of: "-", with: "")
                    .replacingOccurrences(of: " ", with: "")
                if (!query.isEmpty && (norm.contains(query) || query.contains(norm))) {
                    let full = (dir as NSString).appendingPathComponent(item)
                    var isDir: ObjCBool = false
                    if fm.fileExists(atPath: full, isDirectory: &isDir), isDir.boolValue {
                        foundPath = full
                        break
                    }
                }
            }
            if foundPath != nil { break }
        }
        let finalPath = foundPath ?? "/Users/usuario1/Projetos pessoais"
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        proc.arguments = ["-a", "Antigravity IDE", finalPath]
        try? proc.run()
        let dispName = (finalPath as NSString).lastPathComponent.replacingOccurrences(of: "_", with: " ")
        speakNative("Abrindo o projeto \(dispName) no Antigravity, senhor.")
    }

    private func makeWindow() -> NSWindow {
        let size = fullSize
        let rect = frameKeepingPlace(size)
        let window = OverlayWindow(
            contentRect: rect,
            styleMask: [.borderless, .nonactivatingPanel, .fullSizeContentView],
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
        config.userContentController.add(self, name: "jarvisAction")
        let controlsScript = """
        (() => {
          function injectJarvisBar() {
            const oldBar = document.getElementById("jarvisGlobalBar");
            if (oldBar) oldBar.remove();

            if (document.getElementById("macWindowControls")) return;

            if (!document.getElementById("macTrafficLightsStyle")) {
              const style = document.createElement("style");
              style.id = "macTrafficLightsStyle";
              style.textContent = `
                #macWindowControls {
                  position: fixed;
                  top: 14px;
                  left: 14px;
                  display: flex;
                  align-items: center;
                  gap: 8px;
                  z-index: 999999;
                  padding: 0;
                  margin: 0;
                  user-select: none;
                  -webkit-user-select: none;
                  -webkit-app-region: no-drag;
                }
                .traffic-dot {
                  width: 12px;
                  height: 12px;
                  border-radius: 50%;
                  border: none;
                  outline: none;
                  padding: 0;
                  margin: 0;
                  cursor: pointer;
                  position: relative;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  box-shadow: 0 0.5px 1px rgba(0,0,0,0.35);
                  transition: transform 0.1s ease, filter 0.15s ease;
                }
                .traffic-dot:active {
                  transform: scale(0.92);
                }
                .traffic-dot-close {
                  background-color: #ff5f56;
                  border: 0.5px solid #e0443e;
                }
                .traffic-dot-close:active {
                  background-color: #bf4942;
                }
                .traffic-dot-min {
                  background-color: #ffbd2e;
                  border: 0.5px solid #dea123;
                }
                .traffic-dot-min:active {
                  background-color: #bf8e22;
                }
                .traffic-dot-zoom {
                  background-color: #27c93f;
                  border: 0.5px solid #1aab29;
                }
                .traffic-dot-zoom:active {
                  background-color: #1d9730;
                }
                .traffic-dot::after {
                  content: '';
                  position: absolute;
                  opacity: 0;
                  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                  line-height: 12px;
                  text-align: center;
                  transition: opacity 0.15s ease;
                  pointer-events: none;
                }
                #macWindowControls:hover .traffic-dot::after {
                  opacity: 0.75;
                }
                #macWindowControls:hover .traffic-dot:hover::after {
                  opacity: 1;
                }
                .traffic-dot-close::after {
                  content: '✕';
                  font-size: 7.5px;
                  font-weight: 900;
                  color: #4d0000;
                }
                .traffic-dot-min::after {
                  content: '—';
                  font-size: 7.5px;
                  font-weight: 900;
                  color: #5c3b00;
                }
                .traffic-dot-zoom::after {
                  content: '＋';
                  font-size: 7.5px;
                  font-weight: 900;
                  color: #004708;
                }
                .idle-orb #macWindowControls {
                  display: none !important;
                }
              `;
              document.head.appendChild(style);
            }

            const bar = document.createElement("div");
            bar.id = "macWindowControls";
            bar.setAttribute("aria-label", "Controles da janela JARVIS");

            const btnClose = document.createElement("button");
            btnClose.className = "traffic-dot traffic-dot-close";
            btnClose.id = "btnMacClose";
            btnClose.title = "Desligar JARVIS";
            btnClose.setAttribute("aria-label", "Desligar JARVIS");
            btnClose.onclick = (e) => {
              e.stopPropagation();
              try { window.webkit.messageHandlers.jarvisWindow.postMessage("shutdown"); } catch(e){}
            };

            const btnMin = document.createElement("button");
            btnMin.className = "traffic-dot traffic-dot-min";
            btnMin.id = "btnMacMin";
            btnMin.title = "Minimizar para bolinha";
            btnMin.setAttribute("aria-label", "Minimizar para bolinha");
            btnMin.onclick = (e) => {
              e.stopPropagation();
              try { window.webkit.messageHandlers.jarvisWindow.postMessage("minimize"); } catch(e){}
            };

            const btnZoom = document.createElement("button");
            btnZoom.className = "traffic-dot traffic-dot-zoom";
            btnZoom.id = "btnMacZoom";
            btnZoom.title = "Alternar tamanho";
            btnZoom.setAttribute("aria-label", "Alternar tamanho");
            btnZoom.onclick = (e) => {
              e.stopPropagation();
              try { window.webkit.messageHandlers.jarvisWindow.postMessage("zoom"); } catch(e){}
              const extras = document.getElementById("extras");
              if (extras) {
                extras.hidden = !extras.hidden;
              }
            };

            bar.appendChild(btnClose);
            bar.appendChild(btnMin);
            bar.appendChild(btnZoom);
            document.body.appendChild(bar);

            const obs = new MutationObserver(() => {
              const isOrb = document.documentElement.classList.contains("idle-orb");
              bar.style.display = isOrb ? "none" : "flex";
            });
            obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
          }
          if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", injectJarvisBar);
          } else {
            injectJarvisBar();
          }
        })();
        """
        config.userContentController.addUserScript(
            WKUserScript(source: controlsScript, injectionTime: .atDocumentEnd, forMainFrameOnly: true)
        )
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
            replyChip = ""
        } else {
            UserDefaults.standard.set(clipped, forKey: tokenKey)
            if #available(macOS 10.15, *), !CGPreflightScreenCaptureAccess() {
                CGRequestScreenCaptureAccess()
            }
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
