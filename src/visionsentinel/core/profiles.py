"""Assessment profiles.

A profile fixes the budget tier, seed, resource limits, access restrictions, every detector
parameter, calibration provenance and the risk policy. Validation is strict: unknown keys at any
level fail, duplicate YAML keys fail, unknown detector ids fail, and detector parameters are
validated against each detector's own parameter model. The digest of the fully resolved profile is
recorded in every report.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..contracts import Availability, BudgetTier, Capability, Disposition, Layer, Severity
from .errors import ProfileError
from .hashing import digest_json
from .limits import ResourceLimits
from .workspace import repo_root

if TYPE_CHECKING:  # pragma: no cover
    from .registry import DetectorRegistry

_MAX_PROFILE_BYTES = 256 * 1024
_NAME = re.compile(r"^[a-z][a-z0-9_-]{1,40}$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CalibrationConfig(_Strict):
    source: str = Field(description="'uncalibrated', 'literature:<ref>', 'reference-data' or a calibration/*.json path")
    threshold: float | None = None
    threshold_origin: str

    @property
    def calibrated(self) -> bool:
        return self.source != "uncalibrated"


class DetectorConfig(_Strict):
    params: dict[str, Any] = Field(default_factory=dict)
    calibration: CalibrationConfig | None = None


class AccessPolicy(_Strict):
    deny: list[Capability] = Field(default_factory=list)
    note: str = ""


class AnalysisConfig(_Strict):
    resolution: int = Field(default=64, ge=16, le=512)
    encoder_preference: list[Literal["foundation", "reference_model", "classical"]] = Field(
        default_factory=lambda: ["foundation", "reference_model", "classical"]
    )
    batch_size: int = Field(default=64, ge=1, le=4096)
    track_memory: bool = True
    torch_threads: int | None = Field(default=None, ge=1, le=256)


class ContributorPolicy(_Strict):
    prior_strength: float = Field(default=60.0, gt=0, description="Beta prior pseudo-sample count.")
    excess_factor: float = Field(default=2.0, gt=1.0)
    flag_min_confidence: float = Field(default=0.5, ge=0, le=1)
    flag_min_severity: Severity = Severity.LOW
    credible_level: float = Field(default=0.9, gt=0.5, lt=1.0)
    high_anomaly: float = Field(default=0.95, gt=0.5, le=1.0)
    medium_anomaly: float = Field(default=0.8, gt=0.5, le=1.0)
    min_samples: int = Field(default=20, ge=1)


class RuleMatch(_Strict):
    attack_classes: list[str] | None = None
    layers: list[Layer] | None = None
    detectors: list[str] | None = None
    tags: dict[str, str] | None = None
    deterministic: bool | None = None
    calibrated: bool | None = None
    availability: list[Availability] | None = None
    min_severity: Severity | None = None
    max_severity: Severity | None = None
    min_confidence: float | None = Field(default=None, ge=0, le=1)
    max_confidence: float | None = Field(default=None, ge=0, le=1)
    min_corroboration: int | None = Field(default=None, ge=0)


class RuleAction(_Strict):
    disposition: Disposition
    severity: Severity | None = None
    min_severity: Severity | None = None
    max_severity: Severity | None = None
    rationale: str = Field(min_length=8)


class PolicyRule(_Strict):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{1,63}$")
    description: str
    when: RuleMatch
    then: RuleAction


class RiskPolicy(_Strict):
    rules: list[PolicyRule]
    default: RuleAction

    @model_validator(mode="after")
    def _unique(self) -> "RiskPolicy":
        ids = [r.id for r in self.rules]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate policy rule ids: {sorted(dupes)}")
        return self


class Profile(_Strict):
    name: str
    description: str
    budget: BudgetTier
    seed: int = Field(ge=0, lt=2**63)
    access: AccessPolicy = Field(default_factory=AccessPolicy)
    limits: ResourceLimits = Field(default_factory=ResourceLimits)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    detectors: dict[str, DetectorConfig] = Field(default_factory=dict)
    contributors: ContributorPolicy = Field(default_factory=ContributorPolicy)
    risk: RiskPolicy

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not _NAME.match(v):
            raise ValueError("profile name must be lowercase [a-z0-9_-]")
        return v

    @property
    def digest(self) -> str:
        return digest_json(self.model_dump(mode="json"))

    @property
    def policy_digest(self) -> str:
        return digest_json(self.risk.model_dump(mode="json"))

    def detector_config(self, detector_id: str) -> DetectorConfig:
        return self.detectors.get(detector_id) or DetectorConfig()


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys (PyYAML silently keeps the last one)."""


def _construct_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    seen: set[Any] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise ProfileError(f"duplicate key {key!r} at line {key_node.start_mark.line + 1}")
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_yaml_strict(path: Path, *, max_bytes: int = _MAX_PROFILE_BYTES) -> Any:
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise ProfileError(f"{path.name}: larger than {max_bytes} bytes")
    try:
        return yaml.load(data.decode("utf-8"), Loader=_UniqueKeyLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as exc:
        raise ProfileError(f"{path.name}: invalid YAML: {exc}") from exc


def profiles_dir() -> Path:
    return repo_root() / "profiles"


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _resolve(ref: str, seen: tuple[str, ...]) -> dict:
    path = Path(ref)
    if not path.suffix:
        path = profiles_dir() / f"{ref}.yaml"
    if not path.is_file():
        available = ", ".join(sorted(p.stem for p in profiles_dir().glob("*.yaml"))) or "none"
        raise ProfileError(f"profile {ref!r} not found", hint=f"available profiles: {available}")
    key = str(path.resolve())
    if key in seen:
        raise ProfileError(f"profile inheritance cycle: {' -> '.join(seen + (key,))}")
    raw = load_yaml_strict(path)
    if not isinstance(raw, dict):
        raise ProfileError(f"{path.name}: top level must be a mapping")
    parent = raw.pop("extends", None)
    if parent is None:
        return raw
    if not isinstance(parent, str):
        raise ProfileError(f"{path.name}: 'extends' must be a profile name")
    return _deep_merge(_resolve(parent, seen + (key,)), raw)


def load_profile(ref: str | Path, registry: "DetectorRegistry | None" = None) -> Profile:
    """Load, inherit, validate and (optionally) check detector parameters against ``registry``."""
    raw = _resolve(str(ref), ())
    try:
        profile = Profile.model_validate(raw)
    except ValidationError as exc:
        raise ProfileError(_format_validation(exc, str(ref))) from exc
    if registry is not None:
        validate_detector_configs(profile, registry)
    return profile


def validate_detector_configs(profile: Profile, registry: "DetectorRegistry") -> None:
    known = set(registry.ids())
    for det_id, cfg in profile.detectors.items():
        if det_id not in known:
            raise ProfileError(f"profile {profile.name!r}: unknown detector {det_id!r}",
                               hint=f"registered detectors: {', '.join(sorted(known))}")
        params_model = registry.get(det_id).Params
        try:
            params_model.model_validate(cfg.params)
        except ValidationError as exc:
            raise ProfileError(_format_validation(exc, f"{profile.name}:detectors.{det_id}.params")) from exc


def _format_validation(exc: ValidationError, where: str) -> str:
    lines = [f"invalid profile ({where}):"]
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        lines.append(f"  - {loc}: {err['msg']}")
    return "\n".join(lines)


def list_profiles() -> list[str]:
    return sorted(p.stem for p in profiles_dir().glob("*.yaml"))
