"""
Validates real Phase 3 output instances against the actual frozen contract
JSON Schemas (not just a by-eye field-name comparison). Requires the
`jsonschema` package, already a root dependency (see requirements.txt) for
scripts/validate_contracts.py.

This guards against exactly the kind of drift the Phase 1/2 drafts were
flagged as never having verified — e.g. it would have caught
IncidentObservation serializing `tenant_id: null`, which
`incident.schema.json` doesn't allow (that field is plain `{"type":
"string"}`, not nullable) — fixed via `to_contract_dict()` dropping
None-valued fields instead of emitting JSON null.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
from jsonschema import Draft202012Validator  # noqa: E402

from services.anomaly_detection.anomaly_engine import AnomalyObservation
from services.common.phase3_config import Phase3Config
from services.common.phase3_pipeline import Phase3Pipeline
from services.risk_engine.risk_engine import RiskLevel, RiskObservation

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"


def _validate(schema_file: str, instance: dict) -> list[str]:
    schema = json.loads((CONTRACTS_DIR / schema_file).read_text())
    validator = Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(instance)]


@pytest.fixture
def full_chain_result(tmp_path):
    pipeline = Phase3Pipeline(
        Phase3Config(event_confirm_min_observations=1, alert_min_risk_level="HIGH"),
        evidence_base_dir=tmp_path,
    )
    anomaly = AnomalyObservation(track_id=1, anomaly_score=0.9, confidence=0.9, reasons=["speed_deviation"], timestamp=0.0)
    risk = RiskObservation(track_id=1, risk_score=0.95, risk_level=RiskLevel.CRITICAL, confidence=0.9, contributors=["restricted_zone_presence"], timestamp=0.0)
    return pipeline.process_observation(
        track_id=1, camera_id="CAM-1", anomaly=anomaly, risk=risk,
        behaviors=["possible_physical_altercation"], timestamp=1.0, is_restricted_zone=True,
    )


class TestRealContractCompliance:
    def test_event_matches_event_schema(self, full_chain_result):
        errors = _validate("event.schema.json", full_chain_result.event.to_contract_dict())
        assert errors == []

    def test_incident_matches_incident_schema(self, full_chain_result):
        errors = _validate("incident.schema.json", full_chain_result.incident.to_contract_dict())
        assert errors == []

    def test_evidence_matches_evidence_schema(self, full_chain_result):
        errors = _validate("evidence.schema.json", full_chain_result.evidence.to_contract_dict())
        assert errors == []

    def test_alert_matches_alert_schema(self, full_chain_result):
        errors = _validate("alert.schema.json", full_chain_result.alert.to_contract_dict())
        assert errors == []
