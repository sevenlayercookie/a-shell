import Foundation
import ios_system

@main
struct ContinuedProcessingTests {
    static func main() {
        func check(_ condition: @autoclosure () -> Bool, _ message: String) {
            precondition(condition(), message)
        }
        var results: [Bool] = []
        var titles: [(String?, String?)] = []
        let progress = Progress(totalUnitCount: 0)
        let execution = ContinuedCommandExecution(progress: progress, updateTitle: { titles.append(($0, $1)) }, completion: { results.append($0) })
        check(execution.report(.units(20, 100, "Working")), "accept real progress")
        check(progress.completedUnitCount == 20, "publish progress")
        check(titles.last?.1 == "Working", "publish real task description")
        check(!execution.report(.units(19, 100, nil)), "reject backwards work")
        check(execution.report(.percent(50, nil)), "percentage update")
        check(progress.completedUnitCount == 50, "percentage is actual units")
        check(execution.report(.units(Int64.max - 1, Int64.max, nil)), "large unit counts")
        check(execution.report(.percent(100, nil)), "percentage cannot overflow")
        check(progress.completedUnitCount == Int64.max, "large percentage conversion")
        execution.finish(success: true)
        execution.finish(success: false)
        check(results == [true], "complete exactly once")
        check(!execution.report(.subtitle("Late")), "reject late progress")
        let cancelled = ContinuedCommandExecution(progress: Progress(), updateTitle: { _,_ in }, completion: { results.append($0) })
        cancelled.cancel()
        check(cancelled.isCancelled, "cancellation reaches worker")
        check(!cancelled.report(.done), "cancelled work cannot publish success")
        cancelled.finish(success: true)
        check(results == [true, false], "cancellation wins over success")
        let unknown = ContinuedCommandExecution(progress: Progress(), updateTitle: { _,_ in }, completion: { _ in })
        check(unknown.report(.indeterminate(nil)), "allow unknown totals")
        check(unknown.report(.percent(50, nil)), "restore determinate progress")
        check(unknown.progress.completedUnitCount == 50 && unknown.progress.totalUnitCount == 100, "percentage restores meaningful total")
        check(unknown.report(.indeterminate(nil)), "allow returning to unknown total")
        check(unknown.report(.done), "complete unknown total without going backwards")
        check(unknown.progress.completedUnitCount == 50, "preserve completed work")
        let failed = ContinuedCommandExecution(progress: Progress(), updateTitle: { _,_ in }, completion: { results.append($0) })
        failed.finish(success: false)
        check(failed.progress.completedUnitCount == 0, "failure must not claim completed work")
        check(results == [true, false, false], "failure result")
        var labels: [String?] = []
        let timed = ContinuedCommandExecution(progress: Progress(), updateTitle: { labels.append($1) }, completion: { _ in })
        timed.tick(elapsed: 1, command: "python3 job.py")
        let first = timed.progress.completedUnitCount
        check(first > 0 && timed.progress.totalUnitCount == 1_000_000, "default progress starts without a report")
        check(labels.last! == "0:01 · python3 job.py", "default subtitle shows elapsed time")
        timed.tick(elapsed: 3725, command: "python3 job.py")
        check(timed.progress.completedUnitCount > first, "default progress advances")
        check(labels.last! == "1:02:05 · python3 job.py", "elapsed time includes hours")
        for _ in 0..<5 { timed.tick(elapsed: 1e9, command: "x") }
        check(timed.progress.completedUnitCount == 999_999, "default progress never completes")
        check(timed.report(.units(5, 100, "Real")), "real progress replaces default progress")
        check(timed.progress.completedUnitCount == 5 && timed.progress.totalUnitCount == 100, "real progress resets the bar")
        let count = labels.count
        timed.tick(elapsed: 4000, command: "x")
        check(timed.progress.completedUnitCount == 5 && labels.count == count, "default progress stops after a report")
        let titled = ContinuedCommandExecution(progress: Progress(), updateTitle: { _,_ in }, completion: { _ in })
        check(titled.report(.subtitle("Uploading")), "text-only report")
        titled.tick(elapsed: 2, command: "x")
        check(titled.progress.completedUnitCount > 0, "text-only reports keep the default bar moving")
        timed.finish(success: true)
        timed.tick(elapsed: 5000, command: "x")
        check(timed.progress.completedUnitCount == 100, "no default progress after completion")
        let context = strdup("continued-processing-test")!
        defer { free(context) }
        ios_setContext(UnsafeMutableRawPointer(context))
        let routed = ContinuedCommandExecution(progress: Progress(), updateTitle: { _,_ in }, completion: { _ in })
        ProgressCommand.setHandler(for: context, routed.report)
        check(ProgressCommand.execute(["25/100", "Files copied"]) == 0, "script progress routes to task")
        check(routed.progress.completedUnitCount == 25, "routed progress changes task")
        ProgressCommand.setHandler(for: context, nil)
        check(ProgressCommand.execute(["50%"]) == 0, "progress outside a task is a no-op")
        check(routed.progress.completedUnitCount == 25, "removed handler cannot update old task")
        print("PASS continued processing progress, overflow, cancellation, failure, and completion")
    }
}
