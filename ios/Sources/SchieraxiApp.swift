import SwiftUI
import WebKit

/// SchieraXI per iPhone/iPad: una finestra nativa che mostra la web app che gira sul server (raggiungibile con rete privata acceso).
@main
struct SchieraxiApp: App {
    var body: some Scene {
        WindowGroup {
            WebContainer()
                .ignoresSafeArea()
                .background(Color(red: 0.04, green: 0.09, blue: 0.07).ignoresSafeArea())
        }
    }
}

enum Config {
    static func testo(_ chiave: String) -> String {
        (Bundle.main.object(forInfoDictionaryKey: chiave) as? String) ?? ""
    }
    static var host: String { testo("FantaHost") }
    static var url: URL { URL(string: "https://\(host):\(testo("FantaPort"))")! }
}

struct WebContainer: UIViewRepresentable {
    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.limitsNavigationsToAppBoundDomains = true      // abilita i service worker (la web app si apre subito) solo per l'indirizzo dell'app

        let web = WKWebView(frame: .zero, configuration: config)
        let fondo = UIColor(red: 0.04, green: 0.09, blue: 0.07, alpha: 1)
        web.navigationDelegate = context.coordinator
        web.uiDelegate = context.coordinator
        web.allowsBackForwardNavigationGestures = true
        web.scrollView.contentInsetAdjustmentBehavior = .never   // ci pensa la web app con env(safe-area-inset-*)
        web.isOpaque = false
        web.backgroundColor = fondo
        web.scrollView.backgroundColor = fondo

        let tira = UIRefreshControl()
        tira.addTarget(context.coordinator, action: #selector(Coordinator.ricarica), for: .valueChanged)
        web.scrollView.refreshControl = tira

        context.coordinator.web = web
        web.load(URLRequest(url: Config.url))
        return web
    }

    func updateUIView(_ web: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        weak var web: WKWebView?

        @objc func ricarica() {
            if web?.url == nil { web?.load(URLRequest(url: Config.url)) } else { web?.reload() }
        }

        // un link verso un altro sito si apre in Safari, non dentro l'app
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if let url = navigationAction.request.url, let scheme = url.scheme, scheme == "http" || scheme == "https",
               url.host != Config.host {
                UIApplication.shared.open(url)
                decisionHandler(.cancel)
            } else {
                decisionHandler(.allow)
            }
        }

        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if let url = navigationAction.request.url {
                if url.host == Config.host { webView.load(navigationAction.request) } else { UIApplication.shared.open(url) }
            }
            return nil
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { webView.scrollView.refreshControl?.endRefreshing() }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            webView.scrollView.refreshControl?.endRefreshing()
            let pagina = """
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <body style="font-family:-apple-system;background:#0a1812;color:#e8f3ec;text-align:center;padding:30vh 24px 0">
            <h2>Non riesco a raggiungere SchieraXI</h2>
            <p>Controlla che <b>rete privata</b> sia attivo, poi tira giù per riprovare.</p>
            <p style="opacity:.6;font-size:13px">\(error.localizedDescription)</p></body>
            """
            webView.loadHTMLString(pagina, baseURL: nil)
        }

        // alert e conferme della web app
        private func mostra(_ alert: UIAlertController) {
            let scena = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first
            scena?.windows.first(where: { $0.isKeyWindow })?.rootViewController?.present(alert, animated: true)
        }

        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo,
                     completionHandler: @escaping () -> Void) {
            let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
            mostra(a)
        }

        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo,
                     completionHandler: @escaping (Bool) -> Void) {
            let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            a.addAction(UIAlertAction(title: "Annulla", style: .cancel) { _ in completionHandler(false) })
            a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(true) })
            mostra(a)
        }
    }
}
