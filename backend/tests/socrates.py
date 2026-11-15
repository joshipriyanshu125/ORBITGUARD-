import pytest
from datetime import datetime, timezone
from app.services.socrates_service import socrates_service, SocratesConjunctionRecord
from app.models.conjunction import ConjunctionBase, RiskLevel, ConjunctionStatus
from httpx import AsyncClient


def test_parse_socrates_csv():
    raw_csv = """NORAD_CAT_ID_1,OBJECT_NAME_1,NORAD_CAT_ID_2,OBJECT_NAME_2,TCA,MIN_RANGE_KM,REL_VEL_KMS
25544,ISS (ZARYA),39872,FENGYUN 1C DEBRIS,2026-11-16T14:22:15.000Z,1.420,13.850
48274,TIANGONG,34125,COSMOS 2251 DEBRIS,2026-11-16T18:30:00.000Z,3.250,11.500
"""
    records = socrates_service.parse_socrates_text(raw_csv)
    assert len(records) == 2
    assert records[0].primary_norad_id == 25544
    assert records[0].secondary_norad_id == 39872
    assert records[0].min_range_km == 1.420
    assert records[0].rel_vel_kms == 13.850
    assert records[1].primary_norad_id == 48274


def test_socrates_benchmark_comparison():
    # Construct a reference SOCRATES record
    tca_time = datetime(2026, 11, 16, 14, 22, 15, tzinfo=timezone.utc)
    soc_record = SocratesConjunctionRecord(
        primary_norad_id=25544,
        primary_name="ISS (ZARYA)",
        secondary_norad_id=39872,
        secondary_name="FENGYUN 1C DEBRIS",
        tca=tca_time,
        min_range_km=1.420,
        rel_vel_kms=13.850
    )

    # Simulated ORBITGUARD screened event: slight difference (0.05 km range, 2 sec TCA)
    orbitguard_event = ConjunctionBase(
        event_id="CONJ-25544-39872-20261116T142217",
        primary_norad_id=25544,
        primary_name="ISS (ZARYA)",
        secondary_norad_id=39872,
        secondary_name="FENGYUN 1C DEBRIS",
        secondary_type="DEBRIS",
        tca=datetime(2026, 11, 16, 14, 22, 17, tzinfo=timezone.utc),  # 2s delta
        miss_distance_km=1.470,  # 0.05 km delta
        relative_velocity_kms=13.840, # 0.01 km/s delta
        risk_score=88.0,
        risk_level=RiskLevel.HIGH,
        status=ConjunctionStatus.DETECTED
    )

    comparison = socrates_service.compare_screening_with_socrates(
        screened_events=[orbitguard_event],
        socrates_records=[soc_record]
    )

    assert comparison["matched_events_count"] == 1
    match = comparison["matches"][0]
    assert match["tca_delta_seconds"] == 2.0
    assert abs(match["miss_distance_delta_km"] - 0.05) < 1e-3
    assert abs(match["rel_vel_delta_kms"] - 0.01) < 1e-3
    assert match["status"] == "CONCORDANT"
    assert comparison["metrics"]["concordance_score_pct"] > 90.0


def test_socrates_benchmark_service_pipeline():
    # Directly verify benchmark processing against SOCRATES fixture records
    tca_time = datetime(2026, 11, 16, 14, 22, 15, tzinfo=timezone.utc)
    soc_record = SocratesConjunctionRecord(
        primary_norad_id=25544,
        primary_name="ISS (ZARYA)",
        secondary_norad_id=39872,
        secondary_name="FENGYUN 1C DEBRIS",
        tca=tca_time,
        min_range_km=1.420,
        rel_vel_kms=13.850
    )
    orbitguard_event = ConjunctionBase(
        event_id="CONJ-25544-39872-20261116T142217",
        primary_norad_id=25544,
        primary_name="ISS (ZARYA)",
        secondary_norad_id=39872,
        secondary_name="FENGYUN 1C DEBRIS",
        secondary_type="DEBRIS",
        tca=datetime(2026, 11, 16, 14, 22, 17, tzinfo=timezone.utc),
        miss_distance_km=1.470,
        relative_velocity_kms=13.840,
        risk_score=88.0,
        risk_level=RiskLevel.HIGH,
        status=ConjunctionStatus.DETECTED
    )
    res = socrates_service.compare_screening_with_socrates([orbitguard_event], [soc_record])
    assert res["matched_events_count"] == 1
    assert "metrics" in res


@pytest.mark.asyncio
async def test_socrates_api_endpoint(async_client: AsyncClient):
    resp = await async_client.post("/api/conjunctions/socrates/compare")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "summary" in data
    assert data["benchmark_source"] == "CelesTrak SOCRATES"
