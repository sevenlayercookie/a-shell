import Foundation
#if os(iOS)
import BackgroundTasks
import UIKit
#endif

// Kept independent of BackgroundTasks so the command queue can use it on older iOS.
final class ContinuedCommandExecution {
    let progress: Progress
    private let lock = NSLock()
    private var cancelled = false
    private var finished = false
    // Set once the command reports through `progress`; default progress then stops.
    private var reportedUnits = false
    private var reportedText = false
    private let completion: (Bool) -> Void
    private let updateTitle: (String?, String?) -> Void

    init(progress: Progress, updateTitle: @escaping (String?, String?) -> Void,
         completion: @escaping (Bool) -> Void) {
        self.progress = progress
        self.updateTitle = updateTitle
        self.completion = completion
        progress.totalUnitCount = 100
        progress.completedUnitCount = 0
    }

    var isCancelled: Bool {
        lock.lock()
        defer { lock.unlock() }
        return cancelled
    }

    func cancel() {
        lock.lock()
        cancelled = true
        lock.unlock()
    }

    func finish(success: Bool) {
        lock.lock()
        guard !finished else { lock.unlock(); return }
        finished = true
        let succeeded = success && !cancelled
        if succeeded {
            if progress.totalUnitCount <= 0 { progress.totalUnitCount = max(1, progress.completedUnitCount) }
            progress.completedUnitCount = progress.totalUnitCount
        }
        lock.unlock()
        completion(succeeded)
    }

    // Default progress for commands that report none: iOS expires continued tasks that look stalled.
    // The bar advances every tick without ever completing; the subtitle shows the elapsed time.
    func tick(elapsed: TimeInterval, command: String) {
        lock.lock()
        defer { lock.unlock() }
        guard !cancelled, !finished else { return }
        if !reportedUnits {
            let total: Int64 = 1_000_000
            let curve = Int64(Double(total) * (1 - exp(-max(0, elapsed) / 900)))
            progress.totalUnitCount = total
            progress.completedUnitCount = min(total - 1, max(progress.completedUnitCount + 1, curve))
        }
        if !reportedText {
            let seconds = Int(max(0, elapsed))
            let clock = seconds >= 3600
                ? String(format: "%d:%02d:%02d", seconds / 3600, seconds / 60 % 60, seconds % 60)
                : String(format: "%d:%02d", seconds / 60, seconds % 60)
            updateTitle(nil, String("\(clock) · \(command)".prefix(240)))
        }
    }

    // Called by the session-scoped progress command.
    func report(_ update: CommandProgressUpdate) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard !cancelled, !finished else { return false }
        switch update {
        case .title: break
        case .subtitle: reportedText = true
        case .units(_, _, let text), .percent(_, let text), .indeterminate(let text):
            if text != nil { reportedText = true }
            fallthrough
        case .done:
            if !reportedUnits {
                // Real progress replaces the default timer progress.
                reportedUnits = true
                progress.totalUnitCount = 100
                progress.completedUnitCount = 0
            }
        }
        var units: (Int64, Int64)?
        switch update {
        case .units(let done, let total, let text):
            units = (done, total)
            if let text { updateTitle(nil, String(text.prefix(240))) }
        case .percent(let percent, let text):
            let total = progress.totalUnitCount > 0 ? progress.totalUnitCount : 100
            units = (total / 100 * percent + total % 100 * percent / 100, total)
            if let text { updateTitle(nil, String(text.prefix(240))) }
        case .title(let text): updateTitle(String(text.prefix(240)), nil)
        case .subtitle(let text): updateTitle(nil, String(text.prefix(240)))
        case .indeterminate(let text):
            progress.totalUnitCount = -1
            if let text { updateTitle(nil, String(text.prefix(240))) }
        case .done:
            let total = max(1, max(progress.totalUnitCount, progress.completedUnitCount))
            units = (total, total)
        }
        if let (done, total) = units {
            guard total > 0, done >= 0, done <= total,
                  done >= progress.completedUnitCount else { return false }
            progress.totalUnitCount = total
            progress.completedUnitCount = done
        }
        return true
    }
}

#if os(iOS)
@available(iOS 26.0, *)
final class ContinuedProcessing {
    static let shared = ContinuedProcessing()
    private let identifier = Bundle.main.bundleIdentifier! + ".continuedProcessing.shell"
    // Accessed only on the main queue. One reservation covers all terminal windows.
    private var registered = false
    private var start: ((ContinuedCommandExecution) -> Void)?
    private var command = ""
    private var execution: ContinuedCommandExecution?
    private var ticker: DispatchSourceTimer?

    enum SubmissionError: LocalizedError {
        case unavailable, busy, foregroundRequired
        var errorDescription: String? {
            switch self {
            case .unavailable: return "Background processing is unavailable."
            case .busy: return "Another background command is still running."
            case .foregroundRequired: return "Start background commands while a-Shell is in the foreground."
            }
        }
    }

    func register() {
        dispatchPrecondition(condition: .onQueue(.main))
        guard !registered else { return }
        registered = BGTaskScheduler.shared.register(forTaskWithIdentifier: identifier, using: .main) { [weak self] task in
            guard let self, let task = task as? BGContinuedProcessingTask,
                  let start = self.start else {
                task.setTaskCompleted(success: false)
                return
            }
            self.start = nil
            // This flag and all task UI/completion calls belong to the main queue.
            var taskCompleted = false
            let completeTask: (Bool) -> Void = { success in
                guard !taskCompleted else { return }
                taskCompleted = true
                self.ticker?.cancel()
                self.ticker = nil
                task.expirationHandler = nil
                task.setTaskCompleted(success: success)
            }
            let execution = ContinuedCommandExecution(progress: task.progress, updateTitle: { title, subtitle in
                DispatchQueue.main.async {
                    guard !taskCompleted else { return }
                    task.updateTitle(title ?? task.title, subtitle: subtitle ?? task.subtitle)
                }
            }, completion: { [weak self] success in
                DispatchQueue.main.async {
                    completeTask(success)
                    self?.execution = nil
                }
            })
            self.execution = execution
            let began = Date()
            let command = self.command
            let ticker = DispatchSource.makeTimerSource(queue: .main)
            ticker.schedule(deadline: .now() + 1, repeating: 1)
            ticker.setEventHandler { execution.tick(elapsed: Date().timeIntervalSince(began), command: command) }
            ticker.resume()
            self.ticker = ticker
            task.expirationHandler = {
                execution.cancel()
                // Release the system assertion promptly, even if a C command cannot stop yet.
                DispatchQueue.main.async { completeTask(false) }
            }
            start(execution)
        }
    }

    func submit(command: String, start: @escaping (ContinuedCommandExecution) -> Void,
                onFailure: @escaping (Error) -> Void) throws {
        dispatchPrecondition(condition: .onQueue(.main))
        guard registered else { throw SubmissionError.unavailable }
        guard self.start == nil, execution == nil else { throw SubmissionError.busy }
        guard UIApplication.shared.applicationState == .active else { throw SubmissionError.foregroundRequired }
        self.start = start
        self.command = command
        let request = BGContinuedProcessingTaskRequest(identifier: identifier,
            title: "a-Shell command", subtitle: String(command.prefix(240)))
        // A terminal command must either start now or return an error, never run later unexpectedly.
        request.strategy = .fail
        if #available(iOS 27.0, *) {
            // The completion API reports scheduler failures that the older API can miss.
            DispatchQueue.global(qos: .utility).async {
                BGTaskScheduler.shared.submitTaskRequest(request) { error in
                    guard let error else { return }
                    DispatchQueue.main.async {
                        guard self.start != nil else { return }
                        self.start = nil
                        onFailure(error)
                    }
                }
            }
        } else {
            do {
                try BGTaskScheduler.shared.submit(request)
            } catch {
                self.start = nil
                throw error
            }
        }
    }
}
#endif
