# Project SRT — Development Setup

This is the Phase 2 (M6 — DevOps/QA/Production) environment guide. It documents exactly how
to go from a fresh clone to a running, tested, lint-clean development environment. Every
command below has been executed for real during Phase 2 and verified to work.

Windows (PowerShell) is the primary, first-class path (Rule 10 — the team's stated hardware
is Windows/HP Omen). macOS/Linux equivalents are given alongside each step where they differ.

---

## 1. Prerequisites

| Tool | Required version | Why |
|---|---|---|
| Python | 3.11 or 3.12 (3.12 recommended — pinned in `.python-version`) | Backend, services, scripts, tests |
| Node.js | >= 20.19 (LTS or newer) | Frontend (React + TypeScript + Vite) |
| npm | >= 10 (ships with Node 20+) | Frontend package management |
| Git | any recent version | Version control (Rule 8 workflow) |
| NVIDIA GPU + driver | optional | Only relevant once M1/M2 add ML frameworks in a later phase — the environment is fully usable without one (Rule 5) |

You do **not** need Docker, Kubernetes, or any cloud account to complete Phase 2 setup — none
of that is introduced until a later, explicitly-scoped phase.

## 2. Python Version

This repo pins Python via `.python-version` (currently `3.12`). If you use `pyenv`
(macOS/Linux) or `pyenv-win` (Windows), it will pick this up automatically. Otherwise, just
make sure `python --version` / `python3 --version` reports 3.11 or 3.12 before continuing.

## 3. Node.js Version

Install Node.js 20 LTS or newer from https://nodejs.org (Windows installer, or via `nvm-windows`
/ `nvm` on macOS/Linux). Verify:

```powershell
node --version
npm --version
```

## 4. Repository Setup

**Windows (PowerShell):**
```powershell
git clone <repository-url> project-srt
cd project-srt
```

**macOS/Linux (bash/zsh):**
```bash
git clone <repository-url> project-srt
cd project-srt
```

## 5. Backend Environment Setup

Project SRT uses a single shared Python virtual environment at the repo root for all Python
code (backend, scripts, tests) — this keeps things simple for a six-member student team
rather than managing a separate venv per service (Rule 11, Rule 15).

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt -r backend\requirements.txt
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt -r backend/requirements.txt
```

This installs:
- `requirements.txt` — shared runtime tooling (`jsonschema` for contract validation, `python-dotenv`)
- `backend/requirements.txt` — FastAPI runtime (`fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`)
- `requirements-dev.txt` — dev tooling (`pytest`, `pytest-cov`, `httpx`, `black`, `ruff`, `mypy`)

**Start the backend (Phase 2 scope: one `/health` endpoint only — see Rule 3/11):**

```powershell
# from repo root, with .venv activated
cd backend
uvicorn app.main:app --reload --port 8000
```

Then visit `http://127.0.0.1:8000/health` — you should see:
```json
{"status": "ok", "service": "project-srt-backend", "environment": "development"}
```

No other endpoints exist yet. This is expected — real endpoints begin in Phase 3 (M4).

## 6. Frontend Environment Setup

**All platforms (PowerShell / bash / zsh):**
```bash
cd frontend
npm install
```

**Start the frontend dev server:**
```bash
npm run dev
```

Visit the URL Vite prints (typically `http://localhost:5173`) — you should see a page that
says "Project SRT — Frontend development environment ready (Phase 2 scaffold)." No dashboard
features exist yet (Rule 12) — that begins in Phase 22+ (M5).

**Build for production (verifies the toolchain end-to-end):**
```bash
npm run build
```

> **Compatibility note:** `typescript` is pinned to `6.0.3` rather than the newer `7.x` line.
> `typescript-eslint@8.69.0` (the latest published version at the time this was written)
> declares a peer dependency of `typescript >=4.8.4 <6.1.0` — verified via
> `npm view typescript-eslint peerDependencies`. Using TypeScript 7.x breaks `npm install`
> with an `ERESOLVE` conflict. Revisit this pin once `typescript-eslint` publishes TS7 support.

## 7. Environment Variables

Copy the template and fill in local values:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS/Linux:**
```bash
cp .env.example .env
```

`.env` is git-ignored and must **never** be committed (Rule 7). `.env.example` documents every
key with a placeholder value — see that file directly for the current list. Configuration is
environment-driven (`ENVIRONMENT=development|testing|production`, Rule 16); no secrets are
hardcoded anywhere in the codebase.

## 8. Contract Validation

The 23 frozen Contract v1.0 files live in `contracts/` and must never be edited. Validate them
(read-only — this script never writes to any contract file):

```bash
python scripts/validate_contracts.py
```

Expected output ends with `23/23 contracts valid` and `RESULT: PASS`.

## 9. Tests

**Backend/contract tests (pytest):**
```bash
python -m pytest
```
Runs `tests/contracts/test_contracts.py` (validates all 23 contracts) and
`tests/backend/test_health.py` (exercises the real `/health` endpoint). At Phase 2 this is
6 tests, all passing — nothing else exists yet to test (Rule 13).

**Frontend tests (Vitest):**
```bash
cd frontend
npm run test
```
Runs a single smoke test on the Phase 2 placeholder component.

## 10. Lint / Format

**Python:**
```bash
black .              # auto-format
black --check .      # verify formatting without changing files (CI-style)
ruff check .         # lint
mypy backend/app scripts   # type-check (application code only; frontend/node_modules excluded)
```

**TypeScript/React:**
```bash
cd frontend
npm run lint          # ESLint (flat config, eslint.config.js)
npm run format         # Prettier — auto-format
npm run format:check   # Prettier — verify only
npm run typecheck      # tsc --noEmit
```

## 11. GPU Verification

```bash
python scripts/check_gpu.py
```

This script:
1. Runs `nvidia-smi` (if present) to report whether an NVIDIA GPU/driver is visible to the OS.
2. If a Python ML framework happens to already be installed, also reports whether CUDA is
   available to it — **it does not install any framework, model, or weights** (Rule 19).

On the team's primary hardware (HP Omen, GTX 3050) this will report the GPU once the NVIDIA
driver is installed. On a machine with no NVIDIA GPU, it reports that clearly and exits 0 —
this is expected and not an error.

## 12. CPU Fallback

Nothing in Phase 2 requires a GPU. The backend, frontend, tests, contract validation, and
lint/format tooling all run identically on CPU-only machines. GPU-dependent code (model
inference) is introduced only in later phases (M1/M2-owned), and per `docs/ARCHITECTURE.md`
§8, every such stage is required to define a CPU fallback path when it's implemented.

## 13. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `python -m venv .venv` fails or is missing `venv` module | Install the full Python distribution (on Debian/Ubuntu: `sudo apt install python3-venv`); on Windows, use the official python.org installer, which includes `venv`. |
| `pip install ...` fails with `error: externally-managed-environment` | You're installing outside a virtual environment on a system Python. Activate `.venv` first (Step 5) — never install project dependencies into the system Python. |
| `npm install` fails with `ERESOLVE ... typescript-eslint` | You changed the `typescript` version in `frontend/package.json`. Keep it at `6.0.3` (or a version `typescript-eslint`'s peer range allows) until `typescript-eslint` supports TS7 — see the note in §6. |
| `npm run build` fails with `Object literal may only specify known properties, and 'test' does not exist` | `vite.config.ts` must import `defineConfig` from `"vitest/config"`, not `"vite"`, so the Vitest `test` option's types are recognized. This is already done in the committed `vite.config.ts` — only relevant if you're modifying it. |
| `uvicorn: command not found` | `.venv` isn't activated, or `backend/requirements.txt` wasn't installed. Re-run Step 5. |
| `scripts/validate_contracts.py` reports `MISSING` for a contract | A contract file was deleted or renamed locally — restore it from Git; contracts must never be renamed/removed (Rule 1). Do not regenerate a "fixed" version yourself. |
| GPU diagnostic reports "not found on PATH" | Expected on machines without an NVIDIA GPU/driver, or if the driver isn't installed yet. The environment remains fully usable (Rule 5, Rule 19). |
| Formatting/lint tools "fight" each other | Run `black .` and `ruff check --fix .` (Python) or `npm run format` (TS) — they're configured to be compatible, not competing, in this repo's `pyproject.toml` / `eslint.config.js` / `.prettierrc.json`. |

---

## Reproducibility Checklist (Rule 20)

A new team member should be able to, without any undocumented step:

1. `git clone` the repository
2. Install Python 3.12 and Node.js 20+ (§1–3)
3. Create the Python venv (§5)
4. Install backend + shared dependencies (§5) and frontend dependencies (§6)
5. Copy `.env.example` to `.env` (§7)
6. Run `python scripts/validate_contracts.py` → `23/23 ... PASS` (§8)
7. Run `python -m pytest` → all passing, and `cd frontend && npm run test` → passing (§9)
8. Start the backend (`uvicorn app.main:app --reload`) and frontend (`npm run dev`) (§5–6)

All eight steps above were executed for real during Phase 2 and are reflected in the
`PHASE 2 STATUS` report.
