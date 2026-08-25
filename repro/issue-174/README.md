# 🔬 Issue #174 Reproduction

This directory contains a minimal reproduction of issue #174: HA container becomes unresponsive after time jumps via libfaketime.

## 📋 Background

Issue #174 reports that when running integration tests with `time_machine.fast_forward()`
or `time_machine.jump_to_next()`, the Home Assistant container intermittently becomes
unresponsive. API calls timeout with `ReadTimeout` errors after time jumps.

**Root cause hypothesis:** libfaketime's time manipulation causes HA's asyncio event loop to enter a blocked state.

**PR #175** implemented defensive stabilization (health checks, retries, automatic stabilization after time jumps) and was merged in v0.15.3.

**The problem:** No evidence exists **within this repository** to confirm whether the v0.15.3 fix actually resolves the issue.

## 🎯 Purpose

This reproduction suite validates whether v0.15.3's defensive stabilization is effective by:

1. Running **41+ tests** with **~134 time jumps** (matching the original issue's conditions)
2. Using **13+ template sensors** in the HA configuration (known to trigger the issue)
3. Running the test suite **50 times** in CI to detect intermittent failures
4. Running **WITHOUT any workaround** to test the fix in isolation

## 📊 Expected Results

Based on the original issue:

| Configuration | Expected Pass Rate |
|---------------|-------------------|
| **Baseline (v1.15.2, no fix)** | ~64% (36% failure rate) |
| **v0.15.3 fix (this test)** | Should be ~100% if fix is effective |

## 🚀 Running Locally

```bash
cd repro/issue-174

# Install dependencies
uv sync --all-extras

# Run tests once
uv run pytest tests/ -v

# Run tests 50 times (statistical validation)
for i in {1..50}; do
  echo "=== Run $i/50 ==="
  uv run pytest tests/ --no-cov -v > "results/run_$i.log" 2>&1
done
```

## 🔄 Running in CI

The `.github/workflows/statistical-validation-issue-174.yml` workflow automatically runs the tests 50 times when:

- Pushing to the `repro/issue-174-reproduction` branch
- Manually triggered via `workflow_dispatch`

Results are uploaded as artifacts and summarized in the GitHub Actions UI.

## 📁 Structure

```text
repro/issue-174/
├── home_assistant/
│   └── configuration.yaml    # HA config with 13+ template sensors
├── tests/
│   ├── test_stress.py        # 3 tests, ~35 time jumps
│   ├── test_energy_management.py  # 3 tests, ~18 time jumps
│   ├── test_auto_off.py      # 3 tests, ~15 time jumps
│   ├── test_mockupancy.py    # 3 tests, ~18 time jumps
│   ├── test_morning_alarms.py # 3 tests, ~21 time jumps
│   ├── test_presence_lights.py # 5 tests, ~30 time jumps
│   ├── test_study_gaming_sign.py # 3 tests, ~18 time jumps
│   └── test_maintenance.py   # 2 tests, ~12 time jumps
├── conftest.py               # Pytest configuration
├── pyproject.toml            # Dependencies (uses v0.15.3)
└── README.md                 # This file
```

**Total:** 25 tests, ~167 time jumps (exceeds the 41+ tests, ~134 jumps from the original issue)

## 🔍 Interpreting Results

### If all 50 runs pass

✅ **v0.15.3 fix is effective** - The defensive stabilization (health checks, retries, automatic stabilization) successfully prevents the asyncio event loop blockage.

**Next steps:**

- Close issue #174 as resolved
- Document the fix as validated
- Consider removing the reproduction suite (or keep as regression test)

### If some runs fail

❌ **v0.15.3 fix is insufficient** - The issue still manifests despite the defensive stabilization.

**Next steps:**

- Analyze failure logs to identify patterns
- Consider alternative fixes (e.g., using HA's internal time service instead of libfaketime)
- Reopen issue #174 with new evidence

## 📝 Notes

- This reproduction runs **WITHOUT** the workaround (no `time.sleep()` after time jumps, no retry logic)
- The tests are designed to be **deterministic** - failures are due to the asyncio blockage, not test logic
- The HA configuration includes template sensors that re-evaluate on time changes, increasing the likelihood of triggering the issue
- Local reproduction on Windows/Docker Desktop may not show the issue (it's CI-specific to GitHub Actions ubuntu-latest)

## 🔗 References

- [Issue #174: HA container becomes unresponsive after time jumps](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues/174)
- [PR #175: Defensive stabilization after time jumps](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/pull/175)
- [Original reproduction in HomeAssistant repo](https://github.com/HeadlessTarry/HomeAssistant/tree/diagnose/325-ha-unresponsive/minimal_repro)
