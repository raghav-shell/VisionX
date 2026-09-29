"""Governance: acknowledgements, ownership, disposition decisions with a two-person rule, and the audit trail.

Rules (each one is tested as an invariant):
* viewers read; analysts acknowledge, assign, comment and request decisions; approvers also approve/reject;
  admins also manage users;
* tightening a disposition (ACCEPT → REVIEW → QUARANTINE) is applied immediately — escalation is never blocked;
* loosening one is *sensitive*: it stays PENDING until a different person with APPROVER or ADMIN role approves;
  a self-approval attempt is refused and itself recorded in the audit trail;
* a deterministic cryptographic or binding failure can never be set to ACCEPT, by anyone;
* every action is written to the database and appended, Ed25519-signed and hash-chained, to the audit ledger.
"""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select

from ..contracts import Disposition, Role, Severity
from ..core.errors import (AuthorizationError, DecisionAlreadyResolvedError, DecisionNotFoundError,
                           DuplicatePendingDecisionError, GovernanceError, ProtectedFindingError)
from ..provenance.canonical import entry_hash
from ..provenance.ledger import LedgerWriter
from ..storage import AuditEvent, Database, Decision, FindingState, User
from .identity import require_role

REASON_CODES = ("FALSE_POSITIVE", "ACCEPTED_RISK", "REMEDIATED", "DUPLICATE", "NEEDS_INVESTIGATION", "ESCALATION",
                "OTHER")
CRYPTO_CLASSES = frozenset({"record_modification", "record_deletion", "record_reorder", "record_replay",
                            "record_truncation", "signature_forgery", "model_binding_violation", "input_substitution",
                            "config_binding_violation"})
MIN_JUSTIFICATION = 20
MAX_TEXT = 2000
DECISION_PENDING = "PENDING"
DECISION_APPLIED = "APPLIED"
DECISION_APPROVED = "APPROVED"
DECISION_REJECTED = "REJECTED"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AuditTrail:
    db: Database
    ledger: LedgerWriter | None

    def record(self, actor: str, action: str, target: str, *, old: str | None = None, new: str | None = None,
               reason_code: str | None = None, justification: str | None = None, extra: dict | None = None) -> AuditEvent:
        body = {"actor": actor, "action": action, "target": target, "old_state": old, "new_state": new,
                "reason_code": reason_code, "justification": (justification or "")[:MAX_TEXT], **(extra or {})}
        body = {k: v for k, v in body.items() if v is not None}
        rec = self.ledger.append("audit", body) if self.ledger else None
        with self.db.session() as s:
            ev = AuditEvent(actor=actor, action=action, target=target, old_state=old, new_state=new,
                            reason_code=reason_code, justification=(justification or None) and justification[:MAX_TEXT],
                            ledger_seq=rec["seq"] if rec else None, entry_hash=entry_hash(rec) if rec else None)
            s.add(ev)
        return ev


class GovernanceService:
    def __init__(self, db: Database, audit: AuditTrail) -> None:
        self.db = db
        self.audit = audit
        # The application uses one service per process. Serialize governance transitions so
        # concurrent requests cannot both validate the same pending decision before mutation.
        self._transition_lock = threading.RLock()

    # ------------------------------------------------------------------ helpers
    def _finding(self, s, finding_id: str) -> FindingState:
        f = s.get(FindingState, finding_id)
        if f is None:
            raise GovernanceError(f"finding {finding_id} not found")
        return f

    @staticmethod
    def _text(value: str, what: str, minimum: int = 0) -> str:
        value = (value or "").strip()
        if len(value) < minimum:
            raise GovernanceError(f"{what} must be at least {minimum} characters")
        if len(value) > MAX_TEXT:
            raise GovernanceError(f"{what} must be at most {MAX_TEXT} characters")
        return value

    # ------------------------------------------------------------------ light-weight actions
    def acknowledge(self, actor: User, finding_id: str) -> FindingState:
        require_role(actor, Role.ANALYST)
        with self.db.session() as s:
            f = self._finding(s, finding_id)
            old = f.status
            f.acknowledged_by, f.acknowledged_at = actor.username, _now()
            if f.status == "OPEN":
                f.status = "ACKNOWLEDGED"
            new = f.status
        self.audit.record(actor.username, "acknowledge", finding_id, old=old, new=new)
        return f

    def assign(self, actor: User, finding_id: str, owner: str) -> FindingState:
        require_role(actor, Role.ANALYST)
        owner = self._text(owner, "owner", 1)[:64]
        with self.db.session() as s:
            if not s.scalar(select(User).where(User.username == owner)):
                raise GovernanceError(f"unknown user {owner!r}")
            f = self._finding(s, finding_id)
            old, f.owner = f.owner, owner
        self.audit.record(actor.username, "assign_owner", finding_id, old=old, new=owner)
        return f

    def comment(self, actor: User, finding_id: str, text: str) -> None:
        require_role(actor, Role.ANALYST)
        text = self._text(text, "comment", 1)
        with self.db.session() as s:
            self._finding(s, finding_id)
        self.audit.record(actor.username, "comment", finding_id, justification=text)

    # ------------------------------------------------------------------ decisions
    def request_decision(self, actor: User, finding_id: str, to: Disposition, reason_code: str,
                         justification: str) -> Decision:
        with self._transition_lock:
            require_role(actor, Role.ANALYST)
            if reason_code not in REASON_CODES:
                raise GovernanceError(f"reason code must be one of {', '.join(REASON_CODES)}")
            justification = self._text(justification, "justification", MIN_JUSTIFICATION)
            with self.db.session() as s:
                f = self._finding(s, finding_id)
                current = Disposition(f.disposition)
                if to == current:
                    raise GovernanceError(f"finding is already {current.value}")
                if (to == Disposition.ACCEPT and f.deterministic and f.attack_class in CRYPTO_CLASSES
                        and f.severity in {severity.value for severity in (Severity.HIGH, Severity.CRITICAL)}):
                    raise ProtectedFindingError("a deterministic cryptographic or binding failure cannot be accepted; the records "
                                                "concerned remain untrusted regardless of approval")
                if s.scalar(select(Decision).where(Decision.finding_id == finding_id,
                                                   Decision.status == DECISION_PENDING)):
                    raise DuplicatePendingDecisionError("a decision for this finding is already awaiting approval")
                sensitive = to.rank < current.rank
                d = Decision(id="D-" + secrets.token_hex(5).upper(), finding_id=finding_id, scan_id=f.scan_id,
                             requested_by=actor.username, from_disposition=current.value, to_disposition=to.value,
                             reason_code=reason_code, justification=justification, sensitive=sensitive,
                             status=DECISION_PENDING if sensitive else DECISION_APPLIED)
                s.add(d)
                if sensitive:
                    f.status = "PENDING_DECISION"
                else:
                    f.disposition = to.value
                    d.decided_by, d.decided_at = actor.username, _now()
            self.audit.record(actor.username, "request_decision" if sensitive else "apply_escalation", finding_id,
                              old=current.value, new=to.value, reason_code=reason_code, justification=justification,
                              extra={"decision_id": d.id, "sensitive": sensitive})
            return d

    def _decide(self, actor: User, decision_id: str, approve: bool, note: str) -> Decision:
        with self._transition_lock:
            with self.db.session() as s:
                d = s.get(Decision, decision_id)
                if d is None:
                    raise DecisionNotFoundError(f"decision {decision_id} not found")
                requester = d.requested_by
            if actor.username == requester:
                self.audit.record(actor.username, "self_approval_refused", decision_id, old=DECISION_PENDING,
                                  new=DECISION_PENDING,
                                  justification="two-person rule: the requester cannot decide their own request")
                raise AuthorizationError("two-person rule: you cannot approve or reject your own request")
            try:
                require_role(actor, Role.APPROVER)
            except AuthorizationError:
                self.audit.record(actor.username, "approval_refused_role", decision_id, old=DECISION_PENDING,
                                  new=DECISION_PENDING)
                raise
            with self.db.session() as s:
                d = s.get(Decision, decision_id)
                if d is None:
                    raise DecisionNotFoundError(f"decision {decision_id} not found")
                if d.status != DECISION_PENDING:
                    raise DecisionAlreadyResolvedError(f"decision {decision_id} is already resolved")
                f = self._finding(s, d.finding_id)
                d.status = DECISION_APPROVED if approve else DECISION_REJECTED
                d.decided_by, d.decided_at, d.decision_note = actor.username, _now(), note[:MAX_TEXT] if note else None
                old = f.disposition
                if approve:
                    f.disposition = d.to_disposition
                f.status = "DECIDED" if approve else ("ACKNOWLEDGED" if f.acknowledged_by else "OPEN")
                new = f.disposition
            self.audit.record(actor.username, "approve_decision" if approve else "reject_decision", d.finding_id,
                              old=old, new=new, reason_code=d.reason_code, justification=note or None,
                              extra={"decision_id": decision_id, "requested_by": requester})
            return d

    def approve(self, actor: User, decision_id: str, note: str = "") -> Decision:
        return self._decide(actor, decision_id, True, note)

    def reject(self, actor: User, decision_id: str, note: str = "") -> Decision:
        return self._decide(actor, decision_id, False, note)
