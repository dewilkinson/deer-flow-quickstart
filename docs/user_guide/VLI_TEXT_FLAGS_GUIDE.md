# VLI Advanced Text-Flags Guide

The **VLI Command Center** supports powerful, in-line text flags that allow you to bypass or deeply customize the routing architecture of your analysis directly from the prompt. 

These modular flags give institutional users precise control over latency constraints, agentic overrides, and background orchestration.

---

## 1. `--RAW` (Headless Fast-Path)

**Description:** Intentionally circumvents the LangGraph LLM multi-agent reporting suite in favor of maximum speed. It routes the asset directly to the `pandas` and SmartMoneyConcepts analytical engines, returning the unadulterated multi-dimensional computational structures as a pure JSON payload.

**Primary Use Case:** When you need instantaneous (< 2s) quantitative readings for Python script ingestion or dashboard rendering without conversational bloat.

**Execution Impact:**
- **Latency Floor:** ~1.2 seconds.
- **LLM Reasoning:** Disabled.
- **Payload:** Raw Mathematical Arrays.

**Example Command:**
> `/vli analyze NVDA --RAW`

---

## 2. `--BACKGROUND` (Async Synthesis)

**Description:** Decouples the immediate data response from the deep institutional analysis report. When triggered (usually accompanied by `--RAW`), the pipeline will immediately return your fast data metrics while silently spawning a background orchestrator to digest the exact same request. 

**Primary Use Case:** When you need the raw numbers right now to execute a trade, but still want the LangGraph Reporter to compile an extensive institutional brief into your Obsidian Vault's `VLI_Session_Log.md` for later review.

**Execution Impact:**
- **Synchronous Response:** Fast-Path Execution (~2s).
- **Asynchronous Response:** Agentic execution dispatched to `fastapi.BackgroundTasks`.
- **UI Behavior:** Returns `ASYNC_PENDING` badge; frees the UI input buffer immediately.

**Example Command:**
> `/vli analyze AAPL --RAW --BACKGROUND`
> *(Alternatively, use the "ASYNC REPORT" GUI toggle in the Coordinator panel)*

---

## 3. `--FORCE-GRAPH` (Diagnostic Routing)

**Description:** An administrative flag used to intentionally overwhelm the `is_fast_track` heuristics routing protocol in `app.py`. Even if you query using explicitly atomic syntax (like bare `$NVDA` or use `--RAW`), this flag forces the VLI Spine to route the query straight into the LangGraph orchestrator.

**Primary Use Case:** Quality Assurance and Data Consistency Audits. Used to verify that the LLM agent network (`SMC Analyst`, `Reporter`) has perfectly mapped its internal state representations to the raw metric tables without hallucinating.

**Execution Impact:**
- **Routing Status:** Always invokes the Spine Orchestrator. 
- **Latency Overlap:** Invokes the "Reasoning Tax" (~65–85s).
- **Payload:** Dependent on LLM alignment, exposes potential synthesis discrepancies.

**Example Command:**
> `/vli analyze NVDA --RAW --FORCE-GRAPH`

---

### Combination Routing Cheat Sheet

| Command Modifiers | Execution Behavior | Output Destination |
| :--- | :--- | :--- |
| **(None)** | Standard Deep Analysis | Chat Interface & Session Vault |
| **`--RAW`** | Atomic JSON Structure | Output terminal / UI Grid |
| **`--RAW --BACKGROUND`** | Split-Threading: JSON Fast, Text Slow | JSON UI / Vault Telemetry |
| **`--RAW --FORCE-GRAPH`** | Heavy Agentic Stress Test | Diagnostic Logs |
