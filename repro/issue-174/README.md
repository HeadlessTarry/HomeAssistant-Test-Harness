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

This reproduction suite validates whether the issue can be reproduced with v1.15.2 (pre-fix) by:

1. Running **25 tests** with **76 time jumps** (matching the original issue's conditions)
2. Using **13+ template sensors** in the HA configuration (known to trigger the issue)
3. Running the test suite **50 times** in CI to detect intermittent failures
4. Running **WITHOUT any workaround** to test the baseline behavior
5. Using **v1.15.2** (commit d0c86a8, pre-fix version) to establish a failure baseline

## 📊 Expected Results

Based on the original issue:

| Configuration | Expected Pass Rate |
|---------------|-------------------|
| **v1.15.2 (this test)** | ~64% (36% failure rate) |
| **v0.15.3 fix** | Should be ~100% if fix is effective |

**Current test:** Using v1.15.2 (commit d0c86a8) to establish baseline failure rate.

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
├── pyproject.toml            # Dependencies (uses v1.15.2 pre-fix commit d0c86a8)
└── README.md                 # This file
```

**Total:** 25 tests, 76 time jumps

## 🔍 Interpreting Results

### If some runs fail (expected with v1.15.2)

✅ **Issue reproduced** - The asyncio event loop blockage manifests with v1.15.2, confirming the reproduction is valid.

**Next steps:**

- Switch to v0.15.3 to validate the fix
- Compare failure rates between versions

### If all 50 runs pass (unexpected with v1.15.2)

❌ **Issue not reproduced** - The test conditions may not be sufficient to trigger the issue, or the issue may be environment-specific.

**Next steps:**

- Increase number of time jumps
- Add more template sensors
- Check if issue requires specific CI conditions

## 📝 Notes

- This reproduction uses **v1.15.2** (commit d0c86a8, pre-fix) to establish a baseline failure rate
- Runs **WITHOUT** the workaround (no `time.sleep()` after time jumps, no retry logic)
- The tests are designed to be **deterministic** - failures are due to the asyncio blockage, not test logic
- The HA configuration includes template sensors that re-evaluate on time changes, increasing the likelihood of triggering the issue
- Local reproduction on Windows/Docker Desktop may not show the issue (it's CI-specific to GitHub Actions ubuntu-latest)

## 🔗 References

- [Issue #174: HA container becomes unresponsive after time jumps](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues/174)
- [PR #175: Defensive stabilization after time jumps](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/pull/175)
- [Original reproduction in HomeAssistant repo](https://github.com/HeadlessTarry/HomeAssistant/tree/diagnose/325-ha-unresponsive/minimal_repro)
