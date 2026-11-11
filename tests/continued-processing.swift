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
