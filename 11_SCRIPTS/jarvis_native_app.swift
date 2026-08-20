import AppKit
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

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate, WKScriptMessageHandler {
    static var shared: AppDelegate?
    private var window: NSWindow?
    private var webView: WKWebView?

    func applicationDidFinishLaunching(_ notification: Notification) {
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

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {}

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
