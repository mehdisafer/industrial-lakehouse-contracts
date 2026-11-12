class PipelineError(RuntimeError):
    """A stable public code, never an exception containing a credential."""
    code = "PIPELINE_ERROR"

class ContractError(PipelineError):
    code = "INVALID_CONTRACT"

class IntegrityError(PipelineError):
    code = "INTEGRITY_MISMATCH"

class ConflictError(PipelineError):
    code = "IDEMPOTENCY_CONFLICT"

class BusyError(PipelineError):
    code = "PIPELINE_BUSY"

class StaleBaseError(PipelineError):
    code = "STALE_ACCEPTED_BASE"

class CaptureError(PipelineError):
    code = "CAPTURE_UNCERTAIN"

class SourceError(PipelineError):
    code = "SOURCE_CONTRACT_ERROR"

class NativeUnavailable(PipelineError):
    code = "NATIVE_DEPENDENCY_UNAVAILABLE"

class InjectedFailure(PipelineError):
    code = "INJECTED_FAILURE"
