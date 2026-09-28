"""The set of capabilities available to one scan."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts import CAPABILITY_INFO, Capability, CapabilityRecord


@dataclass
class CapabilitySet:
    records: dict[Capability, CapabilityRecord] = field(default_factory=dict)

    @classmethod
    def build(cls, probed: dict[Capability, tuple[str, str | None]], deny: list[Capability] | None = None
              ) -> "CapabilitySet":
        """``probed`` maps capability → (source asset, note). ``deny`` withholds capabilities by policy."""
        deny_set = set(deny or [])
        records: dict[Capability, CapabilityRecord] = {}
        for cap in Capability:
            present = cap in probed
            source, note = probed.get(cap, (None, None))
            records[cap] = CapabilityRecord(
                capability=cap,
                present=present,
                withheld=present and cap in deny_set,
                source=source,
                note=("withheld by profile access policy" if present and cap in deny_set else note),
            )
        return cls(records)

    def has(self, cap: Capability) -> bool:
        rec = self.records.get(cap)
        return bool(rec and rec.present and not rec.withheld)

    def withheld(self, cap: Capability) -> bool:
        rec = self.records.get(cap)
        return bool(rec and rec.withheld)

    def available(self) -> list[Capability]:
        return [c for c in Capability if self.has(c)]

    def as_records(self) -> list[CapabilityRecord]:
        return [self.records[c] for c in Capability]

    def describe(self, cap: Capability) -> str:
        return CAPABILITY_INFO[cap].title
