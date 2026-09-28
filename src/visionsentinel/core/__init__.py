"""Core: registry, capability negotiation, planning, execution, profiles, determinism."""

from .capabilities import CapabilitySet
from .context import BlobSink, DetectorContext
from .detector import Detector, DetectorResult, EmptyParams, Params, PlanContext, SampleFlag, negotiate_spec
from .errors import (
    CapabilityError,
    ConfigurationError,
    EvidenceIntegrityError,
    IntegrityError,
    LoaderError,
    ProfileError,
    ResourceLimitError,
    SandboxError,
    UnsafeInputError,
    VisionSentinelError,
)
from .events import EventLog
from .executor import execute_plan
from .limits import ResourceLimits
from .planner import PlannedCheck, build_plan, plan_counts
from .profiles import CalibrationConfig, Profile, load_profile
from .registry import DetectorRegistry
from .workspace import Workspace

__all__ = [
    "CapabilitySet", "BlobSink", "DetectorContext", "Detector", "DetectorResult", "EmptyParams", "Params",
    "PlanContext", "SampleFlag", "negotiate_spec", "CapabilityError", "ConfigurationError",
    "EvidenceIntegrityError", "IntegrityError", "LoaderError", "ProfileError", "ResourceLimitError",
    "SandboxError", "UnsafeInputError", "VisionSentinelError", "EventLog", "execute_plan", "ResourceLimits",
    "PlannedCheck", "build_plan", "plan_counts", "CalibrationConfig", "Profile", "load_profile",
    "DetectorRegistry", "Workspace",
]
