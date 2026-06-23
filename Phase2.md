# Phase 2 Plan: Add Logging and OpenTelemetry Telemetry

## To‑Do List (high‑level)
1. **Logging and telemetry** – add structured logs and OpenTelemetry instrumentation.
2. **Expose tools as MCP** – make the project's toolset available via the Model Context Protocol.
3. **Trim down requirements** – reduce the `requirements.txt` to only necessary packages.
4. **Improve default agent** – enhance the default executor with better prompts, error handling, and performance.
5. **Complete Alraji agent** – finish implementation of the Alraji specific executor and tests.

## Phase 3 – UI & Telemetry Enhancements
### Containerized OpenTelemetry Collector
* Deploy an OTel Collector container (e.g., `otel/opentelemetry-collector-contrib`).
* Update `otel_setup.py` to point the OTLP exporter to the collector endpoint (`http://localhost:4317`).

### Logging with LogGuru
* Replace the standard `logging` usage with **LogGuru** for easier log formatting and automatic stack traces.
* Add a helper that reads the log level from an environment variable `LOG_LEVEL` (default `INFO`).
* Ensure logs are sent to the OTel collector via the OTLP exporter.

### UI Improvements (app.py / UI components)
* **Add a button** to every output block that lets the user:
  - Re‑use the previous context for a new generation.
  - Start a fresh generation ignoring prior context.
* **Restructure output display**:
  - Introduce a **Current Output** section that shows the most recent result.
  - Below it, render an **All Output** list containing the history of generated outputs.
  - This makes editing or revisiting a single row easier without scrolling through the entire list.

These enhancements will be tackled after completing Phase 2, forming the core of Phase 3.


## Objectives
1. **Add structured logging** across the codebase to capture key events, inputs, outputs, and errors.
2. **Integrate OpenTelemetry (OTel)** to collect traces and metrics, focusing on measuring execution time of critical functions (e.g., `process_row`, `process_mapping_only`, `process_table_group`).
3. **Export telemetry** to a backend (e.g., console, Jaeger, or Prometheus) for observability.
4. Ensure the new instrumentation does not affect existing functionality and can be toggled via configuration.

## Phase‑wise Steps
### Phase 1 – Preparation (already completed)
- Refactored executor to lazily import agents.
- Added `process_mapping_only` shim in `LicExecutor`.

### Phase 2 – Implementation
#### 1. Choose Logging Library
- Use the existing `logging` module (standard library) for simplicity.
- Optionally adopt `structlog` for structured JSON logs if the project prefers.
- Add a central logger configuration file (`logging_config.py`).

#### 2. Add Logger to Core Classes
- Create a base class `BaseExecutor` (or mixin) that provides a `_log` method.
- Ensure `DefaultExecutor`, `LicExecutor`, and `AlrajiExecutor` inherit from it.
- Insert log statements at the start and end of each public method (`process_row`, `process_fsdm_only`, `process_mapping_only`, `process_mapping_custom`, `process_table_group`).
- Log:
  - Function name
  - Input identifiers (e.g., `row_idx`, `table_name`)
  - Success/failure status
  - Exception details when caught.

#### 3. Integrate OpenTelemetry SDK
- Add dependencies to `requirements.txt`:
  ```
  opentelemetry-api
  opentelemetry-sdk
  opentelemetry-instrumentation
  opentelemetry-exporter-otlp
  ```
- Create `otel_setup.py` that:
  - Initializes a `TracerProvider`.
  - Configures a `BatchSpanProcessor` with an OTLP exporter (console or Jaeger).
  - Sets a global tracer via `trace.get_tracer(__name__)`.
  - Provides a helper decorator `@trace_function` to wrap target functions.

#### 4. Instrument Critical Functions
- Apply `@trace_function` (or manual `with tracer.start_as_current_span(...)`) to:
  - `AgentExecutor._get_executor`
  - `DefaultExecutor.process_row` and its overrides.
  - Any long‑running utilities (e.g., DB queries, vector store operations).
- The decorator should record:
  - Start and end timestamps (automatically captured by OTel).
  - Attributes such as `row_idx`, `table_name`, `agent_name`.
  - Exception status.

#### 5. Configuration Toggle
- Add a section in `app.py` or a dedicated config file (`config.yaml` / `settings.py`) with flags:
  ```yaml
  logging:
    level: INFO
    json: true
  telemetry:
    enabled: true
    exporter: console   # or jaeger, otlp
  ```
- The logger and OTel initialization should respect these flags, allowing the feature to be disabled in development.

#### 6. Testing & Validation
- Write unit tests that assert logs are emitted (using `caplog` from pytest).
- Run a small script that triggers the instrumented functions and verify spans appear in the chosen exporter (e.g., console output shows trace IDs and durations).
- Ensure no performance regression > 5 % for typical workloads.

#### 7. Documentation
- Update `README.md` with a **Telemetry** section describing:
  - How to enable/disable.
  - Exporter configuration.
  - Sample logs and trace output.
- Add a quick‑start guide in `docs/USERGUIDE.md` for developers to view telemetry locally (e.g., `docker run -p 16686:16686 jaegertracing/all-in-one`).

## Timeline (estimated)
| Step | Owner | Duration |
|------|-------|----------|
| Logging library selection & config | Dev Lead | 0.5 day |
| Add logger to executors | Backend Engineer | 1 day |
| OTel SDK integration & setup | DevOps / Backend | 1 day |
| Instrument functions | Backend Engineer | 1 day |
| Config toggle & testing | QA Engineer | 0.5 day |
| Documentation update | Tech Writer | 0.5 day |

## Risks & Mitigations
- **Performance impact** – Use asynchronous exporters and batch processing; keep logging level at INFO in production.
- **Sensitive data leakage** – Ensure no PII is logged; mask or omit sensitive fields.
- **Dependency conflicts** – Pin OTel versions compatible with existing packages; run `pip install -r requirements.txt` in a clean virtualenv.

---
*Prepared by the AI coding assistant.*