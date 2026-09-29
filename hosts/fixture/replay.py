"""Run only the fixture's closed, data-driven scenarios."""

import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCENARIOS = ROOT / "scenarios.json"
REGRESSION = ROOT / "regression" / "merge-base-defect.json"


def _classify(name: str) -> str:
    spec = importlib.util.spec_from_file_location("_squatch_fixture_app", ROOT / "app.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("fixture app could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.classify(name)


def replay(name: str | None = None) -> list[dict[str, object]]:
    scenarios = json.loads(SCENARIOS.read_text())
    selected = [scenario for scenario in scenarios if name in (None, scenario["name"])]
    if name is not None and not selected:
        raise ValueError(f"unknown fixture scenario: {name}")
    results = []
    for scenario in selected:
        actual = _classify(scenario["input"])
        expected = scenario["expected"]
        outcome = "pass" if actual == expected else "reproduced"
        result = {"scenario": scenario["name"], "expected": expected,
                  "actual": actual, "outcome": outcome}
        if scenario["name"] == "report-to-regression":
            defect = json.loads(REGRESSION.read_text())
            if outcome == "reproduced" and (
                    defect["input"], defect["expected"], defect["actual"]) != (
                    scenario["input"], expected, actual):
                raise ValueError("regression fixture no longer describes the app")
            result["regression"] = defect
        results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    # The admission smoke check deliberately misses the planted defects.
    # Explicit scenario runs are the defect-sensitive regression checks.
    parser.add_argument("--scenario", default="deterministic-app")
    args = parser.parse_args()
    results = replay(args.scenario)
    print(json.dumps(results, sort_keys=True))
    return int(any(result["outcome"] == "reproduced" for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
