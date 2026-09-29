"""Governance invariants: roles, the two-person rule, crypto findings, and a verifiable audit trail."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from visionsentinel.contracts import Disposition, Role
from visionsentinel.core.errors import AuthorizationError, GovernanceError
from visionsentinel.governance import AuditTrail, GovernanceService, authenticate, create_user, verify_password
from visionsentinel.provenance.ledger import LedgerWriter
from visionsentinel.provenance.trust import load_trust_root
from visionsentinel.provenance.verifier import verify_ledger
from visionsentinel.provenance.workspace_keys import ensure_keys
from visionsentinel.storage import AuditEvent, Database, FindingState, Scan

PW = "correct-horse-battery"


@pytest.fixture()
def gov(workspace):
    db = Database(f"sqlite:///{workspace.root / 'gov.sqlite'}")
    keys = ensure_keys(workspace)
    ledger = LedgerWriter(keys.audit_ledger, keys.audit, purpose="audit", checkpoint_every=8,
                          anchor_path=keys.audit_anchor)
    svc = GovernanceService(db, AuditTrail(db, ledger))
    users = {name: create_user(db, name, PW, role) for name, role in
             (("viewer1", Role.VIEWER), ("analyst1", Role.ANALYST), ("analyst2", Role.ANALYST),
              ("approver1", Role.APPROVER), ("approver2", Role.APPROVER), ("admin1", Role.ADMIN))}
    with db.session() as s:
        s.add(Scan(id="SCN-1", name="t", status="SEALED", profile="baseline"))
        s.flush()
        s.add(FindingState(finding_id="F-DATA", scan_id="SCN-1", detector_id="data.trigger_artifact",
                           attack_class="localized_trigger", layer="DATA", severity="HIGH", original_disposition="QUARANTINE",
                           disposition="QUARANTINE", deterministic=False, title="trigger", confidence=0.9))
        s.add(FindingState(finding_id="F-SIG", scan_id="SCN-1", detector_id="provenance.ledger_integrity",
                           attack_class="record_modification", layer="PROVENANCE", severity="CRITICAL",
                           original_disposition="QUARANTINE", disposition="QUARANTINE", deterministic=True,
                           title="signature", confidence=1.0))
        s.add(FindingState(finding_id="F-MED", scan_id="SCN-1", detector_id="data.ood", attack_class="ood_injection",
                           layer="DATA", severity="MEDIUM", original_disposition="REVIEW", disposition="REVIEW",
                           deterministic=False, title="ood", confidence=0.7))
    return {"svc": svc, "db": db, "users": users, "keys": keys}


JUST = "Visual inspection shows the corner pattern is a sensor graticule, not a trigger."


def _disp(db, fid):
    with db.session() as s:
        return s.get(FindingState, fid).disposition


def test_passwords_are_argon2id_and_login_is_generic(gov):
    u = gov["users"]["analyst1"]
    assert u.password_hash.startswith("$argon2id$") and verify_password(u.password_hash, PW)
    assert authenticate(gov["db"], "analyst1", PW) is not None
    assert authenticate(gov["db"], "analyst1", "wrong-password!") is None
    assert authenticate(gov["db"], "nobody", PW) is None
    with pytest.raises(GovernanceError):
        create_user(gov["db"], "weak", "short", Role.VIEWER)


def test_viewer_cannot_change_anything(gov):
    v = gov["users"]["viewer1"]
    with pytest.raises(AuthorizationError):
        gov["svc"].acknowledge(v, "F-DATA")
    with pytest.raises(AuthorizationError):
        gov["svc"].request_decision(v, "F-DATA", Disposition.ACCEPT, "FALSE_POSITIVE", JUST)


def test_sensitive_reduction_needs_a_second_person(gov):
    svc, u, db = gov["svc"], gov["users"], gov["db"]
    d = svc.request_decision(u["analyst1"], "F-DATA", Disposition.ACCEPT, "FALSE_POSITIVE", JUST)
    assert d.sensitive and d.status == "PENDING" and _disp(db, "F-DATA") == "QUARANTINE"
    with pytest.raises(AuthorizationError, match="two-person"):
        svc.approve(u["analyst1"], d.id)
    with pytest.raises(AuthorizationError):
        svc.approve(u["analyst2"], d.id)  # a second person, but without approval authority
    assert _disp(db, "F-DATA") == "QUARANTINE"
    approved = svc.approve(u["approver1"], d.id, "Confirmed on the raw frames.")
    assert approved.status == "APPROVED" and approved.decided_by == "approver1"
    assert _disp(db, "F-DATA") == "ACCEPT"


def test_an_approver_cannot_approve_their_own_request(gov):
    svc, u = gov["svc"], gov["users"]
    d = svc.request_decision(u["approver1"], "F-DATA", Disposition.REVIEW, "NEEDS_INVESTIGATION", JUST)
    with pytest.raises(AuthorizationError, match="two-person"):
        svc.approve(u["approver1"], d.id)
    svc.reject(u["approver2"], d.id, "Keep quarantined until the supplier answers.")
    assert _disp(gov["db"], "F-DATA") == "QUARANTINE"


def test_escalation_applies_immediately(gov):
    d = gov["svc"].request_decision(gov["users"]["analyst1"], "F-MED", Disposition.QUARANTINE, "ESCALATION", JUST)
    assert not d.sensitive and d.status == "APPLIED" and _disp(gov["db"], "F-MED") == "QUARANTINE"


def test_cryptographic_failure_can_never_be_accepted(gov):
    with pytest.raises(GovernanceError, match="cannot be accepted"):
        gov["svc"].request_decision(gov["users"]["admin1"], "F-SIG", Disposition.ACCEPT, "ACCEPTED_RISK", JUST)


def test_input_validation(gov):
    svc, a = gov["svc"], gov["users"]["analyst1"]
    with pytest.raises(GovernanceError, match="at least"):
        svc.request_decision(a, "F-DATA", Disposition.ACCEPT, "FALSE_POSITIVE", "too short")
    with pytest.raises(GovernanceError, match="reason code"):
        svc.request_decision(a, "F-DATA", Disposition.ACCEPT, "BECAUSE", JUST)
    with pytest.raises(GovernanceError):
        svc.assign(a, "F-DATA", "ghost-user")
    svc.request_decision(a, "F-DATA", Disposition.REVIEW, "NEEDS_INVESTIGATION", JUST)
    with pytest.raises(GovernanceError, match="already awaiting"):
        svc.request_decision(a, "F-DATA", Disposition.ACCEPT, "FALSE_POSITIVE", JUST)


def test_every_action_is_in_a_verifiable_signed_audit_ledger(gov):
    svc, u, db, keys = gov["svc"], gov["users"], gov["db"], gov["keys"]
    svc.acknowledge(u["analyst1"], "F-DATA")
    svc.assign(u["analyst1"], "F-DATA", "analyst2")
    d = svc.request_decision(u["analyst1"], "F-DATA", Disposition.ACCEPT, "FALSE_POSITIVE", JUST)
    with pytest.raises(AuthorizationError):
        svc.approve(u["analyst1"], d.id)
    svc.approve(u["approver2"], d.id, "ok")
    with db.session() as s:
        events = s.scalars(select(AuditEvent).order_by(AuditEvent.id)).all()
    actions = [e.action for e in events]
    assert actions == ["acknowledge", "assign_owner", "request_decision", "self_approval_refused", "approve_decision"]
    assert all(e.entry_hash and e.entry_hash.startswith("sha256:") for e in events)
    req = events[2]
    assert (req.actor, req.old_state, req.new_state, req.reason_code) == ("analyst1", "QUARANTINE", "ACCEPT",
                                                                          "FALSE_POSITIVE")
    svc.audit.ledger.checkpoint()  # export a signed Merkle anchor, as an operator does at shift change
    report = verify_ledger(keys.audit_ledger, load_trust_root(keys.trust_root), anchors=keys.audit_anchor)
    assert report.intact and report.counts["VALID"] >= 6
