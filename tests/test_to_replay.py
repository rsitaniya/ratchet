"""Tests for the raw-records -> /ingest replay spec builder."""
from engagements.madi_onboarding.to_replay import to_specs


def test_preserves_existing_record_id():
    specs = list(to_specs([{"record_id": "r1", "name": "Acme"}], "forbes"))
    assert specs[0]["body"]["record"]["record_id"] == "r1"
    assert specs[0]["meta"]["record_id"] == "r1"


def test_assigns_ordinal_fallback_id_when_absent():
    # Real MaDI-Bench CSVs carry no record_id column at all. Without a fallback,
    # every record hashes identically server-side (str(None)), collapsing
    # distinct records into a single bucket in the integration-gap report.
    records = [{"name": "Acme"}, {"name": "Globex"}]
    specs = list(to_specs(records, "forbes"))
    ids = [s["body"]["record"]["record_id"] for s in specs]
    assert ids == ["forbes-0", "forbes-1"]
    assert len(set(ids)) == len(records)
    # Original records are untouched (no accidental record_id in the source data).
    assert "record_id" not in records[0]
