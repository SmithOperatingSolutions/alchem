# Integrated build/runtime/tooling acceptance

This PR must demonstrate all of the following with executable tests, rather than only API stubs.

- Multi-file builds: relative imports, qualified module calls/references, one entry point, dependency/duplicate/cycle diagnostics, deterministic loading, source locations across files.
- Processes: typed PID capabilities, bounded FIFO mailboxes, spawn/self/send/receive, deadlines, cancellation, joins, immutable shared message data, receive ownership, dead-process behavior and cleanup under race tests.
- Fault tolerance: abnormal-exit capture, monitors/demonitors, symmetric links/unlinks and trapped exits; supervised child identities, permanent/transient/temporary policies, one-for-one/one-for-all/rest-for-one strategies, bounded restart intensity and orderly tree shutdown.
- Tooling: file/line/column compile/runtime diagnostics, Alchem runtime frames including called/imported/anonymous functions, a deterministic idempotent formatter, and CLI/library options for output, targets, build timeout and diagnostics.
- Integration: examples combining imported actors and supervision, negative cases and race/lifecycle stress tests, native Linux/Windows/macOS CI plus six cross-build targets. All checks pass on the final head before marking the PR ready.

Goroutines share an address space. Language cancellation is cooperative at function and closure entry, entry-body statements and runtime waits; it cannot recover from fatal Go runtime errors or forcibly interrupt a blocked operating-system write. These physical limits are explicit contracts, not BEAM isolation claims.

## Evidence matrix

| Area | Executable evidence |
| --- | --- |
| Multi-file modules | `TestProject`, `TestProjectFailures`, `TestStructuredImportPositions`, `TestImportedRuntimeFrames`, `TestIntegratedModuleRuntime` |
| Ownership/mailboxes/deadlines | `TestMailboxOwnershipCopyAndFIFO`, `TestBoundedSendReceiveStop`, `TestBlockedSendersWake`, `TestConstantStackStateLoop`, compiled `processes.alc` |
| Monitors/links | `TestMonitorsLinksAndDemonitor`, `TestUntrappedLinksAndUnlink`, `TestTrappedNormalExit` |
| Supervisor policies/strategies | `TestStrategies`, `TestPoliciesAndIntensity`, `TestRestartWindowAndNestedCleanup`, compiled `supervision.alc` |
| Lifecycle/race cleanup | `TestRaceLifecycle`, repeated `go test -race ./compiler/actor`, generated race-instrumented `examples/system` |
| Runtime diagnostics | `TestRuntimeSourceDiagnostics`, `TestRuntimeDiagnosticInsideFunction`, `TestImportedRuntimeFrames` |
| Formatter and CLI | `TestFormatCompleteGrammar`, `TestCommandsAndFormatting`, `TestFormatterBatchDoesNotModifyOnSyntaxError` |
| Build controls/publication | `TestNoTraceAndReplacement`, `TestBuildToolchainDeadline`, `TestBuildCancellationPreservesOutput`, `TestFailedBuildsNeverPublish`, `TestBuildCannotOverwriteSource` |
| Platform integration | Native race/vet/CLI check/fmt/build/run jobs and six-target CLI plus `examples/system` cross-builds; final run linked in the PR |

All requested areas have executable implementations. Completion is gated by passing this matrix and the final platform CI head; the PR description records the resulting run, rather than treating unexecuted cross binaries as native evidence.
