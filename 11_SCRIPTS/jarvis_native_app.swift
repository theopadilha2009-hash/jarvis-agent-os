import AppKit
import AVFoundation
import CoreAudio
import CoreGraphics
import CoreMedia
import Darwin
import ScreenCaptureKit
import Speech
import WebKit

private let bundleID = "ai.theopadilha.jarvis.cockpit"
private let fallbackURL = "https://jarvis-theo.vercel.app/fala?app=1"

final class PCMConverter {
    private var conversor: AVAudioConverter?

    func convert(_ buffer: AVAudioPCMBuffer, to format: AVAudioFormat) -> AVAudioPCMBuffer? {
        // Comparar valores, não objetos: dois AVAudioFormat diferentes podem
        // representar o mesmo formato. Com `!=` entre objetos o conversor
        // rodava à toa entre formatos idênticos e devolvia silêncio.
        //
        // O interleaving entra na conta: o AVCapture entrega intercalado e o
        // SFSpeech só aceita plano. Só a taxa igual não basta — o buffer
        // passava direto e o reconhecedor respondia "No speech detected".
        if buffer.format.sampleRate == format.sampleRate,
           buffer.format.isInterleaved == format.isInterleaved,
           buffer.format.channelCount == format.channelCount {
            return buffer
        }
        if conversor == nil { conversor = AVAudioConverter(from: buffer.format, to: format) }
        guard let converter = conversor else { return nil }
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
/// Recebe o áudio do AVCaptureSession e entrega como AVAudioPCMBuffer.
///
/// O SpeechAnalyzer trabalha com AVAudioPCMBuffer; o AVCapture entrega
/// CMSampleBuffer. A conversão é só trocar o invólucro — os samples já são
/// float32 mono no formato que o analyzer pediu.
final class CapturaDelegate: NSObject, AVCaptureAudioDataOutputSampleBufferDelegate {
    private let aoChegar: (AVAudioPCMBuffer) -> Void

    init(aoChegar: @escaping (AVAudioPCMBuffer) -> Void) {
        self.aoChegar = aoChegar
    }

    func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        guard let bloco = CMSampleBufferGetDataBuffer(sampleBuffer),
              let formato = CMSampleBufferGetFormatDescription(sampleBuffer),
              let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(formato)
        else { return }
        // O AVCapture entrega PCM de 16 bits por padrão: dividir os bytes por
        // MemoryLayout<Float>.size dava metade das amostras e o
        // floatChannelData vinha nulo — o áudio chegava e sumia.
        let bytes = CMBlockBufferGetDataLength(bloco)
        // Ponteiro de onde saem as amostras: o CMBlockBuffer pode não ser
        // contíguo, então pedir o ponteiro real em vez de copiar às cegas. O
        // CMBlockBufferCopyDataBytes devolvia noErr e deixava o buffer todo
        // zerado — o reconhecedor ficava surdo sem um único erro no log.
        var tamanhoTotal = 0
        var ponteiro: UnsafeMutablePointer<Int8>?
        guard CMBlockBufferGetDataPointer(
            bloco, atOffset: 0, lengthAtOffsetOut: nil, totalLengthOut: &tamanhoTotal, dataPointerOut: &ponteiro
        ) == noErr, let base = ponteiro, tamanhoTotal >= bytes else { return }
        guard bytes > 0, let avFormato = AVAudioFormat(streamDescription: asbd) else { return }
        let porAmostra = max(1, Int(asbd.pointee.mBitsPerChannel) / 8)
        let canais = max(1, Int(asbd.pointee.mChannelsPerFrame))
        let frames = bytes / (porAmostra * canais)
        guard frames > 0,
              let buffer = AVAudioPCMBuffer(
                  pcmFormat: avFormato,
                  frameCapacity: AVAudioFrameCount(frames)
              ),
              let destinoCru = buffer.mutableAudioBufferList.pointee.mBuffers.mData
        else { return }
        buffer.frameLength = buffer.frameCapacity
        memcpy(destinoCru, base, bytes)
        // O AVCapture entrega Float32 intercalado; o resto do app (nível,
        // silêncio, analyzer) trabalha com float desintercalado. O
        // deinterleave acontece aqui, uma vez.
        guard let intercalado = buffer.floatChannelData?[0] else { return }
        if canais > 1 {
            guard let saida = AVAudioPCMBuffer(pcmFormat: avFormato, frameCapacity: buffer.frameLength),
                  let planos = saida.floatChannelData else { return }
            saida.frameLength = buffer.frameLength
            let n = Int(buffer.frameLength)
            for c in 0..<min(canais, Int(avFormato.channelCount)) {
                for i in 0..<n { planos[c][i] = intercalado[i * canais + c] }
            }
            aoChegar(saida)
            return
        }
        aoChegar(buffer)
    }
}

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
    private var engineIniciando = false
    /// Já existe um pipeline de escuta vivo. Impede abrir um segundo quando
    /// o JS pede "start" outra vez.
    private var escutando = false
    /// Sessão de captura quando o áudio vem por AVCapture em vez do engine.
    private var capturaSessao: AVCaptureSession?
    private var delegadoCaptura: CapturaDelegate?
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
    /// Roteiro do vídeo carregado: mantém a janela aberta.
    private var roteiroAtivo = false
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
        } else if message.name == "jarvisSonda" {
            logListen("SONDA \(body)")
        } else if message.name == "jarvisOpen" {
            // O `window.open` do WKWebView devolve null porque a janela nova
            // não é criada: o JS anunciava "Popup bloqueado" no meio da tela
            // em vez de abrir o site. Aqui o link vai direto pro navegador.
            if let url = URL(string: body) { openExternal(url) }
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
                // Só marcar a flag não religa o motor: se ele parou durante a
                // fala, o JARVIS fica surdo para sempre. Foi o que aconteceu
                // no teste com música tocando.
                if !engine.isRunning || task == nil {
                    startListen()
                }
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
        } else if message.name == "jarvisDisplay" {
            // "abre o Google na TV": o navegador não escolhe tela, mas o Mac
            // sabe. O payload traz a URL e o apelido ("tv", "projetor").
            let raw = String(describing: message.body)
            let script = self.displaysScriptPath()
            DispatchQueue.global(qos: .userInitiated).async { [weak self] in
                guard let dados = raw.data(using: .utf8),
                      let pedido = try? JSONSerialization.jsonObject(with: dados) as? [String: Any],
                      let url = pedido["url"] as? String,
                      let tela = pedido["tela"] as? String,
                      !url.isEmpty, !tela.isEmpty else { return }
                let proc = Process()
                proc.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
                proc.arguments = [script, "abrir", url, tela]
                let pipe = Pipe()
                proc.standardOutput = pipe
                try? proc.run()
                proc.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                if let saida = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
                   !saida.isEmpty {
                    DispatchQueue.main.async { self?.speakNative(saida) }
                }
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
                // Vem de fila de fundo: WebKit exige a main.
                DispatchQueue.main.async {
                    self?.webView?.evaluateJavaScript(
                        "window.__jarvisOnScreen && window.__jarvisOnScreen(\(self?.jsString(payload) ?? "\"empty\""))",
                        completionHandler: nil
                    )
                }
            }
        }
    }

    private func resetIdle() {
        idleTimer?.invalidate()
        // Com o roteiro do vídeo carregado a janela não se esconde: o timer
        // de ociosidade fechava a janela e o painel da agenda ia junto,
        // deixando só o orbe bolinha na tela.
        if roteiroAtivo { return }
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

    /// telas.py ao lado do jarvis_actions.py: abre a URL na tela pedida.
    private func displaysScriptPath() -> String {
        let base = (actionsScriptPath() as NSString).deletingLastPathComponent
        return (base as NSString).appendingPathComponent("telas.py")
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

    static func clipForSpeech(_ raw: String, limit: Int) -> String {
        let text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard text.count > limit else { return text }
        let head = String(text.prefix(limit))
        for separator in [". ", ", ", " e "] {
            if let range = head.range(of: separator, options: .backwards) {
                return String(head[..<range.lowerBound]) + "."
            }
        }
        return head
    }

    // MARK: - Ducking da música

    /// Volume do sistema antes de abaixar, para devolver exatamente o mesmo.
    private var volumeAntesDaFala: Int?

    /// Abaixa a música enquanto o JARVIS fala.
    ///
    /// Sem isto a voz compete com o Spotify no volume cheio: no teste o dono
    /// não ouvia o JARVIS e o JARVIS não ouvia o dono. Abaixar para 25% deixa
    /// a música de fundo sem cobrir a fala.
    private func abaixarMusica() {
        // Com a casa dormindo o dono pediu para não mexer no volume: um
        // "abaixa a música" automático no meio da noite acorda quem dorme.
        if UserDefaults.standard.bool(forKey: "jarvisSemMexerNoVolume") { return }
        guard volumeAntesDaFala == nil else { return }
        let atual = Self.volumeDoSistema()
        guard atual > 0 else { return }
        volumeAntesDaFala = atual
        // 25% ainda deixava a música na frente da voz no teste do dono. 15%
        // mantém a trilha audível sem competir com a fala.
        let alvo = max(5, min(atual, Int(Double(atual) * 0.15)))
        Self.definirVolume(alvo)
    }

    /// Devolve o volume que estava antes da fala.
    private func restaurarMusica() {
        guard let anterior = volumeAntesDaFala else { return }
        volumeAntesDaFala = nil
        Self.definirVolume(anterior)
    }

    private static func volumeDoSistema() -> Int {
        let script = NSAppleScript(source: "output volume of (get volume settings)")
        var erro: NSDictionary?
        let resultado = script?.executeAndReturnError(&erro)
        guard erro == nil, let texto = resultado?.stringValue, let valor = Int(texto) else {
            return 0
        }
        return valor
    }

    private static func definirVolume(_ nivel: Int) {
        let seguro = max(0, min(100, nivel))
        let script = NSAppleScript(source: "set volume output volume \(seguro)")
        var erro: NSDictionary?
        _ = script?.executeAndReturnError(&erro)
    }

    private func speakNative(_ raw: String) {
        // 220 no meio da palavra cortava a agenda. Corta no último separador
        // antes do teto — e o servidor já manda um `spoken` curto.
        let text = Self.clipForSpeech(raw, limit: 400)
        guard !text.isEmpty else {
            finishSpeak()
            return
        }
        speechGeneration += 1
        speakingNow = true
        player?.stop()
        // Música de fundo abaixa enquanto ele fala: no teste o Spotify no
        // volume cheio cobria a voz e o dono não entendia.
        abaixarMusica()
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
        // Devolve a música ao volume de antes assim que a fala termina.
        restaurarMusica()
        webView?.evaluateJavaScript("window.__jarvisOnSpeakDone && window.__jarvisOnSpeakDone()", completionHandler: nil)
        resetIdle()
    }

    private func startListen() {
        wantListen = true
        // O JS pede "start" com frequência. Cada pedido criava OUTRO
        // pipeline de transcrição, e três analyzers no mesmo microfone se
        // atropelam (o log mostrava modern listening repetido e nenhuma
        // transcrição). Se já existe um escutando, não cria outro.
        if escutando { return }
        logListen("startListen")
        if #available(macOS 26.0, *), SpeechTranscriber.isAvailable {
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
        escutando = false
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
        // stopModern() zera a flag, então ela vem DEPOIS dele: marcada antes,
        // era apagada na linha seguinte e o JS abria um pipeline por pedido.
        stopModern()
        escutando = true
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
            logListen("reserve ok")
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
                    self?.logListen("ouvido: \(text) (final=\(isFinal))")
                    await MainActor.run {
                        self?.deliverHeard(text, final: isFinal)
                    }
                }
            } catch {
                self?.logListen("results \(error)")
            }
        }
        // Antes de montar o tap: o microfone responde? Se outro app o segura,
        // o startMic travaria a main e o app ficaria surdo sem aviso.
        // Quem manda no microfone é o AVCapture, que abre este HAL onde o
        // engine trava. Só cai no engine se nem o AVCapture existir.
        var entradaMic: AVAudioInputNode?
        var temAparelho = false
        var formatoMic: AVAudioFormat?
        let disponivel: Bool = await withCheckedContinuation { (cont: CheckedContinuation<Bool, Never>) in
            DispatchQueue.global(qos: .userInitiated).async {
                // O AVCaptureDevice às vezes ainda não enxerga o microfone no
                // primeiro segundo do app. Tenta por alguns segundos antes de
                // concluir que não há aparelho.
                var aparelho = AVCaptureDevice.default(for: .audio)
                var tentativas = 0
                while aparelho == nil && tentativas < 6 {
                    Thread.sleep(forTimeInterval: 0.5)
                    aparelho = AVCaptureDevice.default(for: .audio)
                    tentativas += 1
                }
                if let aparelho,
                   let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(
                       aparelho.activeFormat.formatDescription
                   ) {
                    formatoMic = AVAudioFormat(streamDescription: asbd)
                }
                let aut = AVCaptureDevice.authorizationStatus(for: .audio)
                self.logListen("aparelho=\(aparelho?.localizedName ?? "nil") autorizacao=\(aut.rawValue)")
                if aut == .notDetermined {
                    // O status 0 é "nunca perguntaram": o app só consultava e
                    // por isso ficava sem permissão para sempre. Aqui pede.
                    self.logListen("pedindo permissao de microfone")
                    AVCaptureDevice.requestAccess(for: .audio) { liberou in
                        self.logListen("permissao de microfone: \(liberou)")
                        DispatchQueue.main.async {
                            cont.resume(returning: liberou && aparelho != nil)
                        }
                    }
                    return
                }
                temAparelho = aparelho != nil && aut == .authorized
                DispatchQueue.main.async { cont.resume(returning: temAparelho) }
            }
        }
        if !disponivel {
            logListen("microfone indisponivel — sem aparelho ou sem permissao")
        }
        // AVCapture + SFSpeech, não pelo analyzer.
        //
        // O AsyncStream entre a captura e o analyzer era o próprio problema:
        // medido, 16.800 buffers chegavam sem o `yield` e exatamente 1 com ele
        // — o yield bloqueia a fila de entrega do AVCapture e a captura morre
        // no primeiro buffer. O SFSpeech aceita buffer direto e não tem essa
        // fila no caminho, então a captura que já funciona vira transcrição.
        // Só o SFSpeech. O SpeechAnalyzer serializa a entrega e a captura
        // morre no 2º buffer em TODOS os formatos tentados (AsyncStream,
        // fila separada, Task desacoplada, FIFO). O SFSpeech aceita buffer
        // direto, sem stream, e foi o único que transcreveu neste Mac.
        if disponivel, let aparelho = AVCaptureDevice.default(for: .audio) {
            let comecou = await MainActor.run { [weak self] () -> Bool in
                guard let self else { return false }
                self.hadVoiceInCycle = false
                self.silenceStartedAt = 0
                let ok = self.iniciarReconhecimentoAv(aparelho: aparelho)
                if ok {
                    self.tapInstalled = true
                    self.logListen("reconhecendo por AVCapture (\(aparelho.localizedName))")
                    self.tellJS("listening")
                    self.escutando = true
                    self.useModern = false
                }
                return ok
            }
            if comecou { return }
            logListen("AVCapture falhou — caindo no engine")
        }
        guard disponivel else {
            logListen("microfone ocupado — aguardando liberar")
            // Quem reagenda aqui é descartarEngineTravado, numa fila própria.
            // Chamar scheduleRetry daqui não funciona: quando a consulta
            // pendura, a main fica presa e nada enfileirado nela roda.
            return
        }
        guard let entrada = entradaMic else {
            tellJS("microfone_ocupado")
            scheduleRetry()
            return
        }
        await MainActor.run { [weak self] in
            self?.startMic(entrada: entrada, to: analyzerFormat) { buffer in
                continuation.yield(AnalyzerInput(buffer: buffer))
            }
        }
        tellJS("listening")
        escutando = true
        logListen("modern listening")
        do {
            try await analyzer.start(inputSequence: stream)
        } catch {
            logListen("analyzer \(error)")
            // O pipeline morreu: libera a flag para o próximo start criar
            // outro, senão o app fica "escutando" sem escutar.
            escutando = false
            if !Task.isCancelled {
                tellJS("error:\(error.localizedDescription)")
            }
        }
    }

    /// Consulta o microfone fora da main thread, com prazo.
    ///
    /// `engine.inputNode` trava quando outro app segura o microfone com um
    /// diálogo aberto (Blender, Roblox): o HAL bloqueia na primeira consulta
    /// e o log parava calado em "reserve ok", sem nem um erro. Na main thread
    /// isso congela o app e mata o retry — por isso a consulta sai da main.
    /// Devolve o formato de entrada, ou nil se travou.
    @available(macOS 26.0, *)
    private func formatoDoMicComPrazo(_ concluir: @escaping (AVAudioFormat?, AVAudioInputNode?) -> Void) {
        let semaforo = DispatchSemaphore(value: 0)
        var formato: AVAudioFormat?
        var no: AVAudioInputNode?
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self else { semaforo.signal(); return }
            let entrada = self.engine.inputNode
            let fmt = entrada.outputFormat(forBus: 0)
            if fmt.sampleRate > 0 { formato = fmt; no = entrada }
            semaforo.signal()
        }
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            if semaforo.wait(timeout: .now() + 8) == .timedOut {
                guard let self else { return }
                self.logListen("mic travou — outro app segura o microfone")
                // A consulta pendurada prende o engine E a main: qualquer
                // bloco na main depois disso nunca roda. Então nada de
                // DispatchQueue.main aqui — descarta o engine numa fila
                // própria e deixa o retry recriar um limpo.
                self.descartarEngineTravado()
                concluir(nil, nil)
                return
            }
            let resultado = formato
            let noFinal = no
            DispatchQueue.main.async { concluir(resultado, noFinal) }
        }
    }

    /// Descarta o engine quando a consulta do microfone pendurou.
    ///
    /// `engine.inputNode` travado prende o objeto e a main thread junto: a
    /// partir daí nenhum bloco enfileirado na main roda, nem o retry. A saída
    /// é jogar o engine fora e criar outro limpo, numa fila própria, e
    /// reagendar a escuta por lá mesmo.
    private func descartarEngineTravado() {
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self else { return }
            self.engine.stop()
            self.engine = AVAudioEngine()
            self.tapInstalled = false
            self.modernTask?.cancel()
            self.modernTask = nil
            self.escutando = false
            self.logListen("engine recriado — tentando de novo")
            DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + 3) {
                self.startListen()
            }
        }
    }

    @available(macOS 26.0, *)
    private func startMic(entrada: AVAudioInputNode, to analyzerFormat: AVAudioFormat?, yield: @escaping (AVAudioPCMBuffer) -> Void) {
        tearDownRecognition()
        // setVoiceProcessingEnabled trava quando o engine ainda não rodou:
        // o log parava antes de "modern listening" e o app ficava surdo.
        // supressão de eco fica para quando houver um teste com áudio real.
        // O formato já foi consultado com prazo em formatoDoMicComPrazo; aqui
        // só se usa o que veio. Tocar em engine.inputNode de novo na main é
        // o que travava tudo quando outro app segurava o microfone.
        // O formato vem do formatoDoMicComPrazo (já consultado fora da main).
        // Não tocar em engine.inputNode aqui: é justamente essa consulta que
        // trava a main quando outro app segura o microfone.
        guard let micFormat = analyzerFormat, micFormat.sampleRate > 0 else {
            logListen("bad mic format")
            scheduleRetry()
            return
        }
        // O AVAudioEngine trava neste Mac: engine.inputNode pendura o HAL e
        // leva a main junto. AVCaptureSession abre o MESMO microfone sem
        // problema — testado lado a lado, session.isRunning == true onde o
        // engine travava. Ele é o caminho principal; o engine fica de reserva.
        hadVoiceInCycle = false
        silenceStartedAt = 0
        let converter = PCMConverter()
        if iniciarCapturaAv(converter: converter, para: analyzerFormat, yield: yield) {
            tapInstalled = true
            logListen("capturando por AVCapture")
            return
        }
        logListen("AVCapture falhou — tentando o engine")
        let input = entrada
        // O engine inicializa entrada E saída. Com o iMobie virtual como saída
        // padrão o start() trava para sempre — e trava a main thread, então nem
        // o retry roda. Forçar a saída para a placa real do Mac.
        fixarSaidaParaHardware()
        input.installTap(onBus: 0, bufferSize: 4096, format: micFormat) { [weak self] buffer, _ in
            if self?.paused == true { return }
            self?.observeSilence(buffer)
            self?.emitLevel(buffer)
            let out = analyzerFormat.flatMap { converter.convert(buffer, to: $0) } ?? buffer
            yield(out)
        }
        tapInstalled = true
        // start() pode travar (dispositivo ocupado ou driver ruim). Se travar na
        // main thread, o app fica surdo e mudo de vez: chamar numa fila própria.
        startEngineComGuarda()
    }

    /// Captura o microfone por AVCaptureSession.
    ///
    /// O AVAudioEngine pendura neste HAL; o AVCapture não. Cada buffer que
    /// chega passa pelo mesmo caminho do engine — nível, detecção de silêncio
    /// e conversão para o formato do analyzer — então o resto do app não
    /// precisa saber por qual dos dois veio o áudio.
    @available(macOS 26.0, *)
    private func iniciarCapturaAv(
        converter: PCMConverter,
        para analyzerFormat: AVAudioFormat?,
        yield: @escaping (AVAudioPCMBuffer) -> Void
    ) -> Bool {
        guard let aparelho = AVCaptureDevice.default(for: .audio) else { return false }
        let sessao = AVCaptureSession()
        sessao.beginConfiguration()
        guard let entradaAv = try? AVCaptureDeviceInput(device: aparelho),
              sessao.canAddInput(entradaAv) else {
            sessao.commitConfiguration()
            return false
        }
        sessao.addInput(entradaAv)

        let saidaAv = AVCaptureAudioDataOutput()
        let fila = DispatchQueue(label: "jarvis.captura.audio", qos: .userInitiated)
        let delegado = CapturaDelegate { [weak self] buffer in
            guard let self, !self.paused else { return }
            self.observeSilence(buffer)
            self.emitLevel(buffer)
            let out = analyzerFormat.flatMap { converter.convert(buffer, to: $0) } ?? buffer
            yield(out)
        }
        saidaAv.setSampleBufferDelegate(delegado, queue: fila)
        guard sessao.canAddOutput(saidaAv) else {
            sessao.commitConfiguration()
            return false
        }
        sessao.addOutput(saidaAv)
        sessao.commitConfiguration()
        sessao.startRunning()
        guard sessao.isRunning else { return false }
        capturaSessao = sessao
        delegadoCaptura = delegado
        return true
    }

    /// Abre o microfone pelo AVCapture e entrega o áudio ao SFSpeech.
    ///
    /// É o caminho que funciona neste Mac: o engine pendura no HAL e o
    /// analyzer trava na fila de entrega do AVCapture. O SFSpeech recebe
    /// buffer direto, sem stream no meio — o mesmo formato que o analyzer
    /// pediria, só que sem o gargalo.
    private func iniciarReconhecimentoAv(aparelho: AVCaptureDevice) -> Bool {
        guard let recognizer else {
            logListen("sem recognizer")
            return false
        }
        guard recognizer.isAvailable else {
            logListen("recognizer indisponivel")
            tellJS("waiting")
            scheduleRetry()
            return false
        }
        // Nome do app no TCC e status: é o que diz se o reconhecedor é
        // recusado por permissão ou por outra coisa.
        logListen("bundle=\(Bundle.main.bundleIdentifier ?? "nil") nome=\(Bundle.main.infoDictionary?["CFBundleName"] ?? "nil")")
        let pedido = SFSpeechAudioBufferRecognitionRequest()
        pedido.shouldReportPartialResults = true
        pedido.taskHint = .dictation
        if #available(macOS 13.0, *) {
            // Rede de segurança: sem on-device o reconhecedor precisa de rede.
            pedido.requiresOnDeviceRecognition = false
            pedido.contextualStrings = ["Jarvis", "JARVIS", "agenda", "SiteHunter"]
        }
        // Só o analyzer pedia autorização de fala; por este caminho o app
        // ficava com o microfone aberto e o reconhecedor sempre em recusa,
        // sem um erro que dissesse isso.
        logListen("autorizacao de fala=\(SFSpeechRecognizer.authorizationStatus().rawValue)")
        if SFSpeechRecognizer.authorizationStatus() != .authorized {
            SFSpeechRecognizer.requestAuthorization { [weak self] status in
                DispatchQueue.main.async {
                    self?.logListen("speech auth \(status.rawValue)")
                    if status == .authorized {
                        self?.escutando = false
                        self?.fecharCapturaAv()
                        self?.startListen()
                    } else {
                        self?.tellJS("denied")
                    }
                }
            }
            return false
        }
        request = pedido
        let converter = PCMConverter()
        let sessao = AVCaptureSession()
        sessao.beginConfiguration()
        guard let entrada = try? AVCaptureDeviceInput(device: aparelho),
              sessao.canAddInput(entrada) else {
            sessao.commitConfiguration()
            logListen("AVCapture sem entrada")
            return false
        }
        sessao.addInput(entrada)
        let saida = AVCaptureAudioDataOutput()
        // Sem forçar Float32 o AVCapture entrega Int16 e o floatChannelData
        // vem nulo: o áudio chega e some sem erro nenhum.
        saida.audioSettings = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVLinearPCMBitDepthKey: 32,
            AVLinearPCMIsFloatKey: true,
            AVLinearPCMIsNonInterleaved: false,
            AVLinearPCMIsBigEndianKey: false,
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
        ]
        let fila = DispatchQueue(label: "jarvis.captura.reconhecimento", qos: .userInitiated)
        var conta = 0
        let delegado = CapturaDelegate { [weak self] buffer in
            guard let self, !self.paused else { return }
            conta += 1
            if conta <= 2 || conta % 200 == 0 {
                self.logListen("REC #\(conta) frames=\(buffer.frameLength) rms=\(self.bufferRMS(buffer))")
            }
            self.observeSilence(buffer)
            self.emitLevel(buffer)
            guard let atual = self.request else { return }
            self.entregarAoReconhecedor(buffer, pedido: atual, converter: converter)
        }
        saida.setSampleBufferDelegate(delegado, queue: fila)
        guard sessao.canAddOutput(saida) else {
            sessao.commitConfiguration()
            logListen("AVCapture sem saida")
            return false
        }
        sessao.addOutput(saida)
        sessao.commitConfiguration()
        sessao.startRunning()
        guard sessao.isRunning else {
            logListen("AVCapture nao iniciou")
            return false
        }
        capturaSessao = sessao
        delegadoCaptura = delegado
        let task = recognizer.recognitionTask(with: pedido) { [weak self] result, error in
            guard let self else { return }
            if let error {
                DispatchQueue.main.async { self.logListen("task \(error.localizedDescription)") }
            }
            if let texto = result?.bestTranscription.formattedString, !texto.isEmpty {
                let final = result?.isFinal == true
                DispatchQueue.main.async { self.deliverHeard(texto, final: final) }
            }
            if error != nil || result?.isFinal == true {
                // "No speech detected" chega em menos de 1s quando o
                // reconhecedor não recebeu áudio utilizável. Reiniciar na
                // hora virava um laço de 5 ciclos por segundo, cada um
                // derrubando a captura antes de qualquer fala entrar.
                let semFala = (error as NSError?)?.code == 1110
                let espera: TimeInterval = semFala ? 1.5 : 0.2
                DispatchQueue.main.asyncAfter(deadline: .now() + espera) {
                    guard self.wantListen, self.escutando else { return }
                    self.escutando = false
                    self.fecharCapturaAv()
                    self.startListen()
                }
            }
        }
        self.task = task
        logListen("reconhecimento AVCapture ativo")
        return true
    }

    /// Formato que o SFSpeech espera: PCM float 16 kHz mono.
    ///
    /// Precisa ser exatamente o padrão do Core Audio — Float32, plano, 16 kHz
    /// mono. Um AVAudioFormat montado só com commonFormat/rate/channels sai
    /// com flag de assinatura (0x9) e não bate com o formato canônico (0x29):
    /// o conversor devolvia o buffer original e o reconhecedor não entendia.
    private static let formatoReconhecedor: AVAudioFormat? = {
        var asbd = AudioStreamBasicDescription(
            mSampleRate: 16000,
            mFormatID: kAudioFormatLinearPCM,
            mFormatFlags: kAudioFormatFlagIsFloat | kAudioFormatFlagIsPacked | kAudioFormatFlagIsNonInterleaved,
            mBytesPerPacket: 4,
            mFramesPerPacket: 1,
            mBytesPerFrame: 4,
            mChannelsPerFrame: 1,
            mBitsPerChannel: 32,
            mReserved: 0
        )
        return AVAudioFormat(streamDescription: &asbd)
    }()

    private func deintercalar(_ buffer: AVAudioPCMBuffer) -> AVAudioPCMBuffer? {
        guard let alvo = Self.formatoReconhecedor else { return nil }
        let n = Int(buffer.frameLength)
        guard n > 0, let saida = AVAudioPCMBuffer(pcmFormat: alvo, frameCapacity: buffer.frameCapacity) else { return nil }
        saida.frameLength = buffer.frameLength
        guard let destino = saida.floatChannelData?[0] else { return nil }
        if buffer.format.isInterleaved {
            guard let cru = buffer.floatChannelData?[0] else { return nil }
            let canais = max(1, Int(buffer.format.channelCount))
            for i in 0..<n { destino[i] = cru[i * canais] }
        } else {
            guard let plano = buffer.floatChannelData?[0] else { return nil }
            for i in 0..<n { destino[i] = plano[i] }
        }
        return saida
    }

    /// Diagnóstico: o SFSpeech recusa tudo com "No speech detected" mesmo com
    /// fala clara no buffer. Grava o que está sendo entregue para medir se o
    /// problema é o conteúdo ou o formato.
    private static let wavDiagnostico = URL(fileURLWithPath: "/tmp/jarvis-reconhecedor.wav")
    private static var diagnosticoPronto = false
    private var arquivoDiagnostico: AVAudioFile?
    private var gravados = 0
    private func gravarDiagnostico(_ buffer: AVAudioPCMBuffer) {
        guard !Self.diagnosticoPronto else { return }
        // O arquivo fica aberto: recriar a cada buffer truncava o WAV e o
        // diagnóstico saía com 10ms em vez dos 5s entregues.
        if arquivoDiagnostico == nil {
            arquivoDiagnostico = try? AVAudioFile(
                forWriting: Self.wavDiagnostico,
                settings: buffer.format.settings,
                commonFormat: buffer.format.commonFormat,
                interleaved: buffer.format.isInterleaved
            )
        }
        guard let arquivo = arquivoDiagnostico else { return }
        try? arquivo.write(from: buffer)
        gravados += 1
        if gravados >= 500 {
            Self.diagnosticoPronto = true
            logListen("wav de diagnostico gravado: \(Self.wavDiagnostico.path) \(buffer.format.sampleRate)Hz \(buffer.format.channelCount)ch intercalado=\(buffer.format.isInterleaved)")
        }
    }

    private func entregarAoReconhecedor(
        _ buffer: AVAudioPCMBuffer,
        pedido: SFSpeechAudioBufferRecognitionRequest,
        converter: PCMConverter
    ) {
        guard buffer.frameLength > 0 else { return }
        // Se a conversão falha, o buffer NÃO vai no formato errado: vai
        // desintercalado e em float. Mandar o original (intercalado, do
        // AVCapture) é o que fazia o reconhecedor responder "No speech
        // detected" para fala clara — ele aceita e não entende nada.
        var pronto = buffer
        if let alvo = Self.formatoReconhecedor,
           let convertido = converter.convert(buffer, to: alvo),
           convertido.frameLength > 0 {
            pronto = convertido
        } else if let desintercalado = deintercalar(buffer) {
            pronto = desintercalado
        }
        envios += 1
        if envios <= 3 || envios % 300 == 0 {
            logListen("ENVIO #\(envios) frames=\(pronto.frameLength) sr=\(pronto.format.sampleRate) ch=\(pronto.format.channelCount) int=\(pronto.format.isInterleaved) rms=\(bufferRMS(pronto))")
        }
        gravarDiagnostico(pronto)
        pedido.append(pronto)
    }

    private func fecharCapturaAv() {
        if let sessao = capturaSessao {
            if sessao.isRunning { sessao.stopRunning() }
            capturaSessao = nil
        }
        delegadoCaptura = nil
        request?.endAudio()
        request = nil
        task?.cancel()
        task = nil
    }

    /// Aponta a saída do engine para a placa de som do Mac quando o dispositivo
    /// padrão é virtual (iMobie, Soundflower, Loopback). Sem isso o start trava.
    private func fixarSaidaParaHardware() {
        let saida = engine.outputNode
        guard let placa = Self.placaDeSomDoMac() else { return }
        let atual = Self.saidaPadraoDoMac()
        if atual == placa { return }
        do {
            try saida.auAudioUnit.setDeviceID(placa)
            logListen("saida forcada para \(placa) (padrao era \(atual))")
        } catch {
            logListen("nao consegui trocar a saida \(error)")
        }
    }

    /// AudioDeviceID da saída padrão do sistema no momento.
    private static func saidaPadraoDoMac() -> AudioDeviceID {
        var addr = AudioObjectPropertyAddress(
            mSelector: kAudioHardwarePropertyDefaultOutputDevice,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        var devID = AudioDeviceID(0)
        var size = UInt32(MemoryLayout<AudioDeviceID>.size)
        guard AudioObjectGetPropertyData(
            AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &devID
        ) == noErr else { return 0 }
        return devID
    }

    /// AudioDeviceID do alto-falante embutido, se existir.
    private static func placaDeSomDoMac() -> AudioDeviceID? {
        var addr = AudioObjectPropertyAddress(
            mSelector: kAudioHardwarePropertyTranslateUIDToDevice,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        var uid: CFString = "BuiltInSpeakerDevice" as CFString
        var devID = AudioDeviceID(0)
        var size = UInt32(MemoryLayout<AudioDeviceID>.size)
        let status = withUnsafeMutablePointer(to: &uid) { ptr -> OSStatus in
            AudioObjectGetPropertyData(
                AudioObjectID(kAudioObjectSystemObject), &addr,
                UInt32(MemoryLayout<CFString>.size), ptr, &size, &devID
            )
        }
        if status == noErr, devID != 0 { return devID }
        // Plano B: o primeiro dispositivo de saída da fabricante Apple.
        var lista = AudioObjectPropertyAddress(
            mSelector: kAudioHardwarePropertyDevices,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        var bytes = UInt32(0)
        guard AudioObjectGetPropertyDataSize(
            AudioObjectID(kAudioObjectSystemObject), &lista, 0, nil, &bytes
        ) == noErr, bytes > 0 else { return nil }
        var ids = [AudioDeviceID](repeating: 0, count: Int(bytes) / MemoryLayout<AudioDeviceID>.size)
        guard AudioObjectGetPropertyData(
            AudioObjectID(kAudioObjectSystemObject), &lista, 0, nil, &bytes, &ids
        ) == noErr else { return nil }
        for id in ids {
            // "MacBook Air" no nome casa com o microfone também: o que separa
            // alto-falante de microfone é ter canal de saída de verdade.
            guard Self.canaisDeSaida(id) > 0 else { continue }
            var nomeAddr = AudioObjectPropertyAddress(
                mSelector: kAudioObjectPropertyName,
                mScope: kAudioObjectPropertyScopeGlobal,
                mElement: kAudioObjectPropertyElementMain
            )
            var nome: CFString = "" as CFString
            var nSize = UInt32(MemoryLayout<CFString>.size)
            guard AudioObjectGetPropertyData(id, &nomeAddr, 0, nil, &nSize, &nome) == noErr else { continue }
            let rotulo = nome as String
            // "iMobie" e afins são virtuais: nunca servir de saída do engine.
            if rotulo.localizedCaseInsensitiveContains("iMobie") { continue }
            if rotulo.localizedCaseInsensitiveContains("MacBook")
                || rotulo.localizedCaseInsensitiveContains("Alto-falantes")
                || rotulo.localizedCaseInsensitiveContains("Speakers") {
                return id
            }
        }
        return nil
    }

    /// Quantos canais de saída o dispositivo tem (0 = só entrada, ou nenhum).
    private static func canaisDeSaida(_ id: AudioDeviceID) -> Int {
        var addr = AudioObjectPropertyAddress(
            mSelector: kAudioDevicePropertyStreamConfiguration,
            mScope: kAudioDevicePropertyScopeOutput,
            mElement: kAudioObjectPropertyElementMain
        )
        var tamanho = UInt32(0)
        guard AudioObjectGetPropertyDataSize(id, &addr, 0, nil, &tamanho) == noErr,
              tamanho > 0 else { return 0 }
        let bruto = UnsafeMutableRawPointer.allocate(
            byteCount: Int(tamanho), alignment: MemoryLayout<AudioBufferList>.alignment
        )
        defer { bruto.deallocate() }
        guard AudioObjectGetPropertyData(id, &addr, 0, nil, &tamanho, bruto) == noErr else { return 0 }
        let lista = UnsafeMutableAudioBufferListPointer(
            bruto.assumingMemoryBound(to: AudioBufferList.self)
        )
        return lista.reduce(0) { $0 + Int($1.mNumberChannels) }
    }

    /// start() fora da main thread, com timeout: travou, derruba e tenta de novo.
    private func startEngineComGuarda() {
        guard !engineIniciando else { return }
        engineIniciando = true
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self else { return }
            let semaforo = DispatchSemaphore(value: 0)
            var falha: Error?
            DispatchQueue.global(qos: .userInitiated).async {
                do { try self.engine.start() } catch { falha = error }
                semaforo.signal()
            }
            if semaforo.wait(timeout: .now() + 8) == .timedOut {
                self.logListen("engine.start travou — reiniciando")
                self.engine.stop()
                DispatchQueue.main.async {
                    self.engineIniciando = false
                    self.scheduleRetry()
                }
                return
            }
            DispatchQueue.main.async {
                self.engineIniciando = false
                if let falha {
                    self.logListen("engine \(falha)")
                    self.scheduleRetry()
                } else {
                    self.logListen("mic sr=\(self.engine.inputNode.outputFormat(forBus: 0).sampleRate)")
                }
            }
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

    /// Reagenda a escuta depois de uma falha.
    ///
    /// `Timer.scheduledTimer` depende do run loop da main estar girando; vindo
    /// de dentro de uma Task async ele nunca disparava e o app parava de
    /// tentar depois do primeiro erro — ficava vivo e surdo para sempre.
    /// `asyncAfter` na main sempre entrega.
    private func scheduleRetry() {
        retryTimer?.invalidate()
        retryTimer = nil
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) { [weak self] in
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
        // A captura por AVCapture é dona da sessão: fechar aqui é o que evita
        // duas sessões no mesmo microfone quando o ciclo reinicia.
        fecharCapturaAv()
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
    /// Quantos buffers já foram entregues ao reconhecedor neste app.
    private var envios = 0

    // Padrão Handy: auto-stop por silêncio. Depois de voz detectada (RMS acima
    // do piso), 1.8s contínuos abaixo do piso fecham a captura corrente — o
    // parcial pendente é entregue como final e o ciclo recomeça pelos caminhos
    // que já existiam (clássico reinicia no recognitionTask; moderno reinicia
    // o pipeline pelo mesmo caminho do restart do JS). Sem voz nova, nada
    // acontece: a escuta contínua por wake word segue intacta.
    /// Limiar de "tem voz aqui".
    ///
    /// Medido no microfone deste Mac, com o tap aberto:
    ///   silêncio de sala — p50 0.0003, máximo 0.0035
    ///   fala a 40cm    — p50 0.0020, p90 0.035, máximo 0.047
    /// 0.012 fica acima do pico de ruído em uso real (o app fechava frase a
    /// cada 8s com a sala em silêncio no limiar de 0.006) e abaixo do corpo
    /// da fala (p75 0.026). O 0.02 anterior cortava as sílabas fracas; este
    /// não, porque só a fala sustentada passa.
    private let silenceRmsFloor: Float = 0.012
    /// Espera antes de fechar a frase. 1,8s cortava no meio de uma frase com
    /// pausa natural ("sim... pode abrir"); 2,6s ainda fechava entre frases
    /// de uma fala normal. 3,5s dá tempo da pausa ser pausa, não fim.
    private let silenceStopAfter: TimeInterval = 3.5
    private var hadVoiceInCycle = false
    private var voiceProcessingOn = false
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
        // Ciclo novo SEMPRE: o reconhecedor encerra o pedido quando o áudio
        // para de fazer sentido para ele, e a partir daí a captura entrega
        // um ou dois buffers e trava. Reciclar a cada pausa mantém o
        // microfone vivo por todo o vídeo em vez de morrer na primeira
        // frase.
        reciclarEscuta()
    }

    private func reciclarEscuta() {
        DispatchQueue.main.async { [weak self] in
            guard let self, self.wantListen, self.escutando else { return }
            self.logListen("reciclando a escuta")
            self.escutando = false
            self.stopModern()
            self.tearDownRecognition()
            self.startListen()
        }
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

    /// A pausa na fala só precisa fechar a frase, não derrubar o pipeline.
    ///
    /// A versão anterior chamava stopModern/startListen a cada pausa: cada
    /// volta custava ~0,35s de áudio perdido mais o tempo de recriar o
    /// analyzer, e o log enchia de "silence stop" + CancellationError. O
    /// reconhecedor já entrega o texto parcial sozinho; basta sinalizar o
    /// fim do enunciado e seguir ouvindo no mesmo stream.
    private func finalizeModernOnSilence() {
        guard wantListen, useModern else { return }
        // Não reinicia nada: só avisa quem escuta que a frase terminou. Se o
        // reconhecedor já mandou um final, o deliverHeard ignora o repetido.
        tellJS("utterance_end")
        hadVoiceInCycle = false
        silenceStartedAt = 0
        logListen("frase fechada")
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
        // WKWebView não é thread-safe: chamar de fila de fundo derrubava o app
        // com EXC_BAD_ACCESS na main, dentro do RemoteLayerTree do WebKit.
        // Várias chamadas (mic ocupado, frase fechada) vêm de filas próprias.
        let script = "window.__jarvisNativeListen && window.__jarvisNativeListen(\(jsString(state)))"
        if Thread.isMainThread {
            webView?.evaluateJavaScript(script, completionHandler: nil)
        } else {
            DispatchQueue.main.async { [weak self] in
                self?.webView?.evaluateJavaScript(script, completionHandler: nil)
            }
        }
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
        // Desligar exige a frase inteira, não um trecho solto.
        //
        // O microfone capta o eco do alto-falante: numa conversa qualquer ele
        // transcreveu "ah tá cê vai dormir ah não então" e se desligou no meio
        // do teste. Exigir a frase curta e completa evita o desligamento
        // acidental sem tirar o comando de quem realmente quer fechar.
        let desligar = ["desliga o jarvis", "desligar o jarvis", "fecha o jarvis",
                        "fechar o jarvis", "desliga jarvis", "desligar jarvis",
                        "fecha jarvis", "fechar jarvis", "vai dormir jarvis",
                        "pode dormir jarvis", "desligar completamente"]
        if desligar.contains(where: { clean == $0 || clean.hasSuffix(" " + $0) }) {
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
        config.userContentController.add(self, name: "jarvisOpen")

        // Diagnóstico do palco do vídeo: mostra no log o que o painel da
        // agenda respondeu. Sem isto o painel falhava calado.
        let sonda = """
        (() => {
          window.__jarvisSonda = (msg) => {
            try { window.webkit.messageHandlers.jarvisSonda.postMessage(String(msg)); } catch(e) {}
          };
        })();
        """
        config.userContentController.addUserScript(
            WKUserScript(source: sonda, injectionTime: .atDocumentStart, forMainFrameOnly: true)
        )
        config.userContentController.add(self, name: "jarvisSonda")

        // Roteiro do vídeo: injeta a fala no JARVIS como se ele tivesse
        // ouvido. O microfone deste Mac entrega áudio que o reconhecedor
        // descarta, e o dono precisa gravar agora — os dados falsos são
        // trocados pelo caminho real depois.
        let caminho = "/tmp/jarvis-roteiro.txt"
        if let texto = try? String(contentsOfFile: caminho, encoding: .utf8), !texto.isEmpty {
            roteiroAtivo = true
            // Formato: uma linha por fala, "<segundos até esta fala>|<frase>".
            for linha in texto.split(separator: "\n") {
                let partes = linha.split(separator: "|", maxSplits: 1)
                guard partes.count == 2, let segundos = Double(partes[0]) else { continue }
                let frase = String(partes[1]).replacingOccurrences(of: "'", with: "\\'")
                DispatchQueue.main.asyncAfter(deadline: .now() + segundos) { [weak self] in
                    guard let self, let webView = self.webView else { return }
                    // A janela abre em modo bolinha; sem sair dele o vídeo
                    // não mostra nada além do orbe.
                    self.revealWindow(takeFocus: true)
                    webView.evaluateJavaScript(
                        "window.__jarvisDizer && window.__jarvisDizer('\(frase)')",
                        completionHandler: nil
                    )
                }
            }
        }
        config.userContentController.add(self, name: "jarvisListen")
        config.userContentController.add(self, name: "jarvisRestart")
        config.userContentController.add(self, name: "jarvisWindow")
        config.userContentController.add(self, name: "jarvisSee")
        config.userContentController.add(self, name: "jarvisAction")
        config.userContentController.add(self, name: "jarvisDisplay")
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

    /// Tela onde o JARVIS mora: a segunda do arranjo do dono.
    ///
    /// Ele montou três telas — Spotify na primeira, a web do JARVIS na
    /// segunda, GitHub na terceira. A janela nasce na segunda e não fica
    /// pulando para a principal a cada abertura.
    private func telaDoJarvis() -> NSScreen? {
        let telas = NSScreen.screens
        guard telas.count > 1 else { return NSScreen.main }
        // Ordena por posição horizontal: a segunda da esquerda para a direita.
        let ordenadas = telas.sorted { $0.frame.minX < $1.frame.minX }
        return ordenadas[1]
    }

    private func frameKeepingPlace(_ size: NSSize) -> NSRect {
        let screen = telaDoJarvis()?.visibleFrame ?? activeScreenFrame()
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
