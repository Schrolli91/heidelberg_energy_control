# Tests

Pytest suite for the Heidelberg Energy Control integration. Tests are characterization tests — they pin today's behavior so refactors (capability framework, new feature groups) can be reviewed against an executable contract rather than a prose description.

## Setup

```bash
python3 -m venv .venv-test
.venv-test/bin/pip install -r requirements_test.txt
```

Python 3.13+ recommended (matches the CI workflow). The venv lives at the repo root and is `.gitignore`'d.

## Running

```bash
# whole suite
.venv-test/bin/pytest tests/ -v

# single file
.venv-test/bin/pytest tests/test_api_decoding.py -v

# single test
.venv-test/bin/pytest tests/test_api_decoding.py::test_polled_data_decoding_full_dict -v

# only a specific parametrized variant
.venv-test/bin/pytest tests/ -v -k "v2.0.4-real"

# stop at first failure, full traceback
.venv-test/bin/pytest tests/ -x --tb=long

# show print/log output even when tests pass
.venv-test/bin/pytest tests/ -s
```

## Layout

| File | What it pins |
|---|---|
| `test_api_decoding.py` | Modbus wire-format: raw register lists → `async_get_data()` / `async_get_static_data()` dicts. Parametrized across all captured fixtures. |
| `test_coordinator_virtual.py` | The bidirectional sync between the virtual enable switch, virtual target current slider, and hardware register 261. Includes empty-response tolerance. |
| `test_coordinator_is_supported.py` | Firmware-version gating semantics (fail-open on missing/unparseable versions, `>=` comparison, virtual-logic gate at v1.0.7). |
| `conftest.py` | `load_fixture()`, `build_mock_modbus_client()`, and the `mock_api` fixture used by coordinator tests. |
| `fixtures/wallbox_*.json` | Captured register values from real or synthetic wallboxes. |

## Fixtures and variants

`test_api_decoding.py` is parametrized over a `VARIANTS` list. Each entry is a `pytest.param(fixture_name, expected_static, expected_polled, id=...)` triple. The decoder runs against every variant on every test run, so a regression shows up against the whole captured envelope, not just one device.

Current variants:

- **`v1.0.7-synthetic`** — hand-crafted 3-phase actively-charging state. Exercises the multi-phase math, 32-bit energy decoding, and non-trivial state values.
- **`v2.0.4-real`** — real capture from a connect-series wallbox (single-phase install, idle at minimum target current). Exercises real-hardware decoding.

### Adding a new fixture

To add a third (e.g. a v1.0.8 device, or a v2.0.4 capture during active charging):

1. **Capture from the wallbox.** From the repo root:

   ```bash
   .venv-test/bin/python scripts/capture_fixture.py \
       --host <wallbox-ip> --port 502 --device-id 1 \
       --out tests/fixtures/wallbox_<label>.json
   ```

   The script reads every register the integration currently touches and writes the result as JSON. Register values are non-sensitive — commit the fixture.

2. **Add a variant in `test_api_decoding.py`.** Append a `VARIANT_<LABEL>` entry to the `VARIANTS` list with the expected static and polled dicts.

3. **Derive the expected values.** Either work them out from the captured registers and `core/api.py`'s decoding rules, or run `pytest` once with placeholder values, read the actual decoded dict out of the failure diff, and paste it in.

4. **Re-run the suite.** Both characterization tests now cover the new variant.

## Known gotchas

- **pymodbus 3.x requires a running event loop at `AsyncModbusTcpClient.__init__()` time.** That's why pure-function tests in `test_api_decoding.py` are declared `async` even though they only call static-style helpers — pytest-asyncio's loop must be active for the constructor to succeed. If you add a sync test that instantiates the API class, it will fail with `RuntimeError: no running event loop`. Make it `async` or construct the client lazily.

- **The `mock_api` fixture in `conftest.py` does not implement the Modbus wire protocol.** It's a `MagicMock` whose `async_get_data` and `async_write_register` are `AsyncMock`s. Coordinator tests configure return values per case. For tests that need the real API class with a mock client (e.g. wire-format decoding), use the `_make_api(fixture_name)` helper in `test_api_decoding.py`.

- **`mock_modbus_client` returns an error response for any read it wasn't preconfigured for.** This is intentional — silently returning empty data would let tests pass against accidental register accesses that don't exist on the fixture. If a new register is read in `core/api.py`, the corresponding entry must be added to `build_mock_modbus_client` in `conftest.py`.
