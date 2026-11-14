import Foundation
import ios_system

/// Prototype: hands one URL to the system download service (a background URLSession), which
/// transfers it outside the app. It exists to measure whether that is faster than downloading
/// inside a-Shell while the app is not on screen. One download at a time, no state across launches.
final class SystemDownload: NSObject, URLSessionDownloadDelegate {
    static let shared = SystemDownload()
    private let lock = NSLock()
    private var current = -1  // identifier of the task this run started; other tasks are ignored
    private var received: Int64 = 0
    private var expected: Int64 = 0
    private var destination: URL?
    private var outcome: String?  // nil while running, "" on success, otherwise the error
    private var finishEvents: (() -> Void)?
    private lazy var session: URLSession = {
        let configuration = URLSessionConfiguration.background(withIdentifier: (Bundle.main.bundleIdentifier ?? "a-Shell") + ".download")
        // Discretionary transfers wait for the system's convenience; this one was asked for now.
        configuration.isDiscretionary = false
        configuration.sessionSendsLaunchEvents = true
        return URLSession(configuration: configuration, delegate: self, delegateQueue: nil)
    }()

    /// The system relaunched or woke the app because transfers finished while it was suspended.
    func resumeEvents(_ completion: @escaping () -> Void) {
        lock.lock()
        finishEvents = completion
        lock.unlock()
        _ = session
    }

    func cancelAll() {
        session.getAllTasks { $0.forEach { $0.cancel() } }
    }

    func start(_ url: URL, to destination: URL) {
        cancelAll()
        let task = session.downloadTask(with: url)
        lock.lock()
        current = task.taskIdentifier
        received = 0
        expected = 0
        outcome = nil
        self.destination = destination
        lock.unlock()
        task.resume()
    }

    var state: (received: Int64, expected: Int64, outcome: String?) {
        lock.lock()
        defer { lock.unlock() }
        return (received, expected, outcome)
    }

    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didWriteData bytesWritten: Int64,
                    totalBytesWritten: Int64, totalBytesExpectedToWrite: Int64) {
        lock.lock()
        defer { lock.unlock() }
        guard downloadTask.taskIdentifier == current else { return }
        received = totalBytesWritten
        expected = totalBytesExpectedToWrite
    }

    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didFinishDownloadingTo location: URL) {
        lock.lock()
        defer { lock.unlock() }
        guard downloadTask.taskIdentifier == current, let destination else { return }
        // The temporary file disappears when this method returns.
        do {
            try? FileManager.default.removeItem(at: destination)
            try FileManager.default.moveItem(at: location, to: destination)
            if let status = (downloadTask.response as? HTTPURLResponse)?.statusCode, !(200..<300).contains(status) {
                outcome = "HTTP status \(status)"
            }
        } catch {
            outcome = error.localizedDescription
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        lock.lock()
        defer { lock.unlock() }
        guard task.taskIdentifier == current else { return }
        received = max(received, task.countOfBytesReceived)
        outcome = error?.localizedDescription ?? outcome ?? ""
    }

    func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
        lock.lock()
        let completion = finishEvents
        finishEvents = nil
        lock.unlock()
        DispatchQueue.main.async { completion?() }
    }
}

@_cdecl("ashell_download")
public func ashellDownload(argc: Int32, argv: UnsafeMutablePointer<UnsafeMutablePointer<CChar>?>?) -> Int32 {
    var arguments = (1..<max(1, Int(argc))).compactMap { index -> String? in
        guard let argument = argv?[index] else { return nil }
        return String(cString: argument)
    }
    let usage = "Usage: download [-o file] url\n       download cancel\nThe system transfers the file outside the app. Speeds are logged to download.log.\n"
    if arguments == ["cancel"] {
        SystemDownload.shared.cancelAll()
        return 0
    }
    var output: String?
    if arguments.count == 3, arguments[0] == "-o" {
        output = arguments[1]
        arguments.removeFirst(2)
    }
    guard arguments.count == 1, let url = URL(string: arguments[0]), ["http", "https"].contains(url.scheme ?? "") else {
        fputs(usage, thread_stderr)
        return 2
    }
    let directory = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    let name = output ?? (url.lastPathComponent.isEmpty || url.lastPathComponent == "/" ? "download" : url.lastPathComponent)
    let destination = URL(fileURLWithPath: name, relativeTo: directory).absoluteURL
    let megabyte = 1048576.0
    let formatter = DateFormatter()
    formatter.dateFormat = "HH:mm:ss"
    FileManager.default.createFile(atPath: directory.appendingPathComponent("download.log").path, contents: nil)
    let log = FileHandle(forWritingAtPath: directory.appendingPathComponent("download.log").path)
    SystemDownload.shared.start(url, to: destination)
    let began = Date()
    var last = began
    var previous: Int64 = 0
    while true {
        Thread.sleep(forTimeInterval: 1)
        let (received, expected, outcome) = SystemDownload.shared.state
        let now = Date()
        let gap = now.timeIntervalSince(last)
        let speed = Double(received - previous) / megabyte / gap
        // The app does not run while suspended, so a long gap is one sample covering that time.
        let line = String(format: "%@ +%5.1fs %6.1f MB/s %7.0f MB%@", formatter.string(from: now), gap, speed,
                          Double(received) / megabyte, gap > 3 ? " SUSPENDED" : "")
        log?.write((line + "\n").data(using: .utf8)!)
        fputs("\r\u{1b}[K" + line + (expected > 0 ? String(format: " of %.0f MB", Double(expected) / megabyte) : ""), thread_stdout)
        fflush(thread_stdout)
        last = now
        previous = received
        if let outcome {
            let seconds = now.timeIntervalSince(began)
            fputs(String(format: "\n%@: %.0f MB in %.0fs, average %.1f MB/s. See download.log\n",
                         outcome.isEmpty ? "Saved \(name)" : "Failed (\(outcome))",
                         Double(received) / megabyte, seconds, Double(received) / megabyte / seconds), thread_stdout)
            return outcome.isEmpty ? 0 : 1
        }
    }
}
