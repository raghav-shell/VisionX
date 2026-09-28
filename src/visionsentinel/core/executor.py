"""Plan execution with failure isolation.

A detector exception is recorded as ``ERROR`` with its type and message and never downgraded to
``UNAVAILABLE``. Dependants of a failed detector are also ``ERROR`` (their inputs are missing because
something broke, not because access was absent).
"""

from __future__ import annotations

import logging
import resource
import time
import tracemalloc
from collections.abc import Callable
from contextlib import contextmanager

from ..contracts import Availability, DetectorExecution, ExecutionState
from .context import DetectorContext
from .detector import DetectorResult
from .events import EventLog
from .planner import PlannedCheck

log = logging.getLogger(__name__)

ContextFactory = Callable[[PlannedCheck, dict[str, DetectorResult]], DetectorContext]


@contextmanager
def _memory_probe(enabled: bool):
    box = {"peak": 0}
    started_here = False
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    if enabled:
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            started_here = True
        tracemalloc.reset_peak()
    try:
        yield box
    finally:
        peak = 0
        if enabled and tracemalloc.is_tracing():
            peak = tracemalloc.get_traced_memory()[1]
            if started_here:
                tracemalloc.stop()
        rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        box["peak"] = max(peak, rss_after - rss_before)


def execute_plan(plan: list[PlannedCheck], make_context: ContextFactory, events: EventLog, *,
                 track_memory: bool = True) -> tuple[list[DetectorExecution], dict[str, DetectorResult]]:
    results: dict[str, DetectorResult] = {}
    states: dict[str, ExecutionState] = {}
    executions: list[DetectorExecution] = []

    for check in plan:
        spec = check.detector.spec
        neg = check.negotiation
        base = dict(detector_id=spec.id, detector_version=spec.version, title=spec.title, layer=spec.layer,
                    planned=neg.availability, mode=neg.mode,
                    calibrated=(check.calibration.calibrated if check.calibration else None))

        if not check.runnable:
            executions.append(DetectorExecution(**base, state=ExecutionState.NOT_RUN, reasons=neg.reasons))
            states[spec.id] = ExecutionState.NOT_RUN
            continue

        failed = [d for d in spec.depends_on if states.get(d) == ExecutionState.ERROR]
        if failed:
            msg = "upstream detector failed: " + ", ".join(failed)
            executions.append(DetectorExecution(**base, state=ExecutionState.ERROR, reasons=[msg],
                                                error_type="UpstreamFailure", error_message=msg))
            states[spec.id] = ExecutionState.ERROR
            events.emit(f"{spec.title}: not executed — {msg}", level="error", detector_id=spec.id)
            continue
        idle = [d for d in spec.depends_on if states.get(d) in (ExecutionState.ABSTAINED, ExecutionState.NOT_RUN)]
        if idle:
            msg = "upstream detector produced no result: " + ", ".join(idle)
            executions.append(DetectorExecution(**base, state=ExecutionState.ABSTAINED, reasons=[msg]))
            states[spec.id] = ExecutionState.ABSTAINED
            events.emit(f"{spec.title}: abstained — {msg}", level="warn", detector_id=spec.id)
            continue

        suffix = f" [{neg.mode}]" if neg.mode else ""
        events.emit(f"{spec.title} started{suffix}", detector_id=spec.id)
        ctx = make_context(check, results)
        t0 = time.perf_counter()
        with _memory_probe(track_memory) as mem:
            try:
                result = check.detector.run(ctx)
                error: BaseException | None = None
            except Exception as exc:  # noqa: BLE001 - isolation boundary, recorded as ERROR
                result = None
                error = exc
        runtime_ms = (time.perf_counter() - t0) * 1000.0

        if error is not None or result is None:
            log.exception("detector %s failed", spec.id, exc_info=error)
            executions.append(DetectorExecution(
                **base, state=ExecutionState.ERROR, runtime_ms=runtime_ms, peak_memory_bytes=mem["peak"],
                reasons=["detector raised an exception during execution"],
                error_type=type(error).__name__ if error else "NoResult",
                error_message=(str(error) or repr(error))[:800] if error else "detector returned no result",
            ))
            states[spec.id] = ExecutionState.ERROR
            events.emit(f"{spec.title} FAILED — {type(error).__name__}: {error}", level="error", detector_id=spec.id)
            continue

        if result.abstained:
            state = ExecutionState.ABSTAINED
            assessed = []
            reasons = [result.abstained]
            events.emit(f"{spec.title} abstained — {result.abstained}", level="warn", detector_id=spec.id)
        else:
            state = (ExecutionState.COMPLETED_DEGRADED if neg.availability == Availability.DEGRADED
                     else ExecutionState.COMPLETED)
            assessed = result.assessed_override if result.assessed_override is not None else neg.assessed_classes
            reasons = list(neg.reasons) + list(result.notes)
            events.emit(f"{spec.title} complete — {len(result.findings)} finding(s), "
                        f"{result.samples_processed} item(s) in {runtime_ms / 1000:.2f}s", detector_id=spec.id)
        executions.append(DetectorExecution(
            **base, state=state, reasons=reasons, assessed_classes=assessed, runtime_ms=runtime_ms,
            samples_processed=result.samples_processed, peak_memory_bytes=mem["peak"],
            findings=len(result.findings), metrics=result.metrics,
        ))
        states[spec.id] = state
        results[spec.id] = result
    return executions, results
