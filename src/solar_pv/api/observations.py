"""CSV and JSON interchange for Student 1 inspection observations."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, fields

from solar_pv.domain.observations import Observation


SCHEMA_VERSION = "0.2"
PHASE4_VERSION = "0.3"
PHASE4_FIELDS = (
    "measurement_basis", "temperature_unit", "minimum_temperature", "maximum_temperature",
    "mean_temperature", "median_temperature", "reference_temperature", "delta_temperature",
    "sample_count", "excluded_sample_count", "thermal_region_bounds",
    "thermal_reference_bounds", "calibration_reference", "observation_category",
    "finding_status", "severity", "created_at_utc", "modified_at_utc",
    "scada_source_file", "scada_scope", "scada_timezone_status", "correlation_status",
    "correlation_missing",
)
CSV_FIELDS = ("schema_version", *(field.name for field in fields(Observation) if field.name not in PHASE4_FIELDS))
CSV_FIELDS_V03 = ("schema_version", *(field.name for field in fields(Observation)))


def observations_csv(observations: list[Observation]) -> str:
    return _observations_csv(observations, CSV_FIELDS, SCHEMA_VERSION)


def observations_csv_v03(observations: list[Observation]) -> str:
    return _observations_csv(observations, CSV_FIELDS_V03, PHASE4_VERSION)


def _observations_csv(observations: list[Observation], fieldnames: tuple[str, ...], version: str) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for observation in observations:
        row = {key: value for key, value in asdict(observation).items() if key in fieldnames}
        row["schema_version"] = version
        row["data_quality_flags"] = ";".join(observation.data_quality_flags)
        if "correlation_missing" in row:
            row["correlation_missing"] = ";".join(observation.correlation_missing)
        writer.writerow(row)
    return output.getvalue()


def observations_json(observations: list[Observation]) -> str:
    return _observations_json(observations, SCHEMA_VERSION, include_phase4=False)


def observations_json_v03(observations: list[Observation]) -> str:
    return _observations_json(observations, PHASE4_VERSION, include_phase4=True)


def _observations_json(observations: list[Observation], version: str, *, include_phase4: bool) -> str:
    return json.dumps(
        {
            "schema_version": version,
            "observations": [
                {key: value for key, value in asdict(observation).items() if include_phase4 or key not in PHASE4_FIELDS}
                for observation in observations
            ],
        },
        indent=2,
    ) + "\n"
