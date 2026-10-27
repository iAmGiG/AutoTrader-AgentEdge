"""The #539 exit-rule family in the multiple-testing audit."""

import importlib
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def audit(monkeypatch):
    monkeypatch.syspath_prepend(str(REPO / "scripts" / "research"))
    return importlib.import_module("multiple_testing_audit")


def _exit_json(path, p_values):
    tests = [
        {
            "comparison": "trailing - bracket",
            "variant": "moderate",
            "period": "full",
            "cost_bps": cost,
            "return_test": {"mean_daily_diff": 1e-5 * (i + 1), "t_statistic": 2.0, "p_value": p},
        }
        for i, (cost, p) in enumerate(zip([0.0, 5.0, 10.0], p_values))
    ]
    tests.append({"comparison": "trailing - bracket", "variant": "moderate", "return_test": None})
    path.write_text(json.dumps({"paired_tests": tests}))


def test_collector_reads_the_runners_paired_tests(audit, monkeypatch, tmp_path):
    _exit_json(tmp_path / "trailing_vs_bracket.json", [0.5, 0.04, 0.9])
    monkeypatch.setattr(audit, "STRATEGY_RESULTS_DIR", tmp_path)
    rows = []

    audit.collect_trailing_exits(rows)

    assert [r["p_value"] for r in rows] == [0.5, 0.04, 0.9]  # a test without a statistic is skipped
    assert {r["study"] for r in rows} == {"#539 trailing - bracket (moderate)"}
    assert rows[1]["test"] == "full 5 bps daily return (NW)"
    assert rows[1]["effect"] == pytest.approx(2e-5)
    assert rows[0]["source"] == "trailing_vs_bracket.json"


def test_collector_leaves_out_the_morning_raise_sensitivity(audit, monkeypatch, tmp_path):
    path = tmp_path / "trailing_vs_bracket.json"
    _exit_json(path, [0.5, 0.04, 0.9])
    data = json.loads(path.read_text())
    sensitivity_test = {
        "comparison": "trailing+morning - bracket",
        "variant": "moderate",
        "period": "full",
        "cost_bps": 5.0,
        "return_test": {"mean_daily_diff": -1e-4, "t_statistic": -2.5, "p_value": 0.01},
    }
    data["morning_raise_sensitivity"] = {
        "paired_tests_vs_bracket": [sensitivity_test],
        "effect_of_morning_raise": [
            dict(sensitivity_test, comparison="trailing+morning - trailing")
        ],
    }
    path.write_text(json.dumps(data))
    monkeypatch.setattr(audit, "STRATEGY_RESULTS_DIR", tmp_path)
    rows = []

    audit.collect_trailing_exits(rows)

    # only the runner's paired_tests: the sensitivity repeats those hypotheses, it adds none
    assert [r["p_value"] for r in rows] == [0.5, 0.04, 0.9]
    assert {r["study"] for r in rows} == {"#539 trailing - bracket (moderate)"}


def test_collector_tolerates_a_missing_file(audit, monkeypatch, tmp_path):
    monkeypatch.setattr(audit, "STRATEGY_RESULTS_DIR", tmp_path)
    rows = []

    audit.collect_trailing_exits(rows)

    assert rows == []


def test_exit_tests_are_corrected_as_a_family_and_pooled_with_the_gex_family(audit):
    exit_rows = [
        audit._row("#539 x", "f", f"t{i}", 3.0, p) for i, p in enumerate([0.001, 0.2, 0.9])
    ]
    gex_rows = [audit._row("GEX", "g", f"t{i}", 0.0, 0.3 + i / 1000) for i in range(200)]

    out = audit.exit_rule_family(exit_rows, gex_rows)

    assert out["issue"] == "#539"
    summary = out["summary"]
    assert (summary["n_tests"], summary["holm_rejections"]) == (3, 1)  # 0.001 x 3 < 0.05
    assert summary["pooled_with_gex_family"]["n_tests"] == 203
    assert summary["pooled_with_gex_family"]["exit_tests_holm_rejections"] == 0  # 0.001 x 203
    assert [s["study"] for s in out["by_study"]] == ["#539 x"]
    assert len(out["tests"]) == 3 and out["tests"][0]["p_value"] == 0.001


def test_gex_family_is_corrected_as_before(audit):
    rows = [audit._row("s", "f", f"t{i}", 2.0, p) for i, p in enumerate([0.001, 0.01, 0.2, 0.8])]

    df, summary, by_study = audit._correct(rows)

    assert list(df["p_value"]) == [0.001, 0.01, 0.2, 0.8]  # sorted by p
    assert summary == {
        "n_tests": 4,
        "raw_p_below_0.05": 2,
        "expected_by_chance_at_0.05": 0.2,
        "holm_rejections": 2,  # 0.001 x 4, 0.01 x 3
        "bh_rejections": 2,
        "abs_t_above_3": 0,
    }
    assert by_study.to_dict(orient="records") == [
        {"study": "s", "n": 4, "raw": 2, "holm": 2, "bh": 2, "t3": 0}
    ]


def test_collector_skips_a_test_without_a_finite_statistic(audit, monkeypatch, tmp_path):
    path = tmp_path / "trailing_vs_bracket.json"
    _exit_json(path, [0.5, float("nan"), 0.9])
    monkeypatch.setattr(audit, "STRATEGY_RESULTS_DIR", tmp_path)
    rows = []

    audit.collect_trailing_exits(rows)

    assert [r["p_value"] for r in rows] == [0.5, 0.9]  # a NaN would poison the family's correction
