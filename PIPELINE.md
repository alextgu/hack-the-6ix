# Pipeline — two model seams. Do not merge them.

The system has **two independent model call sites**. They must never be
confused, cross-wired, or consolidated behind one function.

- **Read seam** — `brain.py::call_model()` — **Gemini, permanently.**
  Turns messy group chat into structured trip constraints. Wins the Gemini track.
- **Agent seam** — `phoebe.py::agent_call()` — **Freesolo (post-training).**
  Reads the constraints Read produced, diagnoses the ONE binding blocker,
  and acts (DM a holdout / propose cheaper neighborhood / hold rooms 48h).
  Wins the Freesolo track.

Data flow (linear, one direction only):

```
messages ─▶ brain.py (Gemini) ─▶ state.py {constraints + blocker flags}
                                          │
                                          ▼
                             phoebe.py (Freesolo) ─▶ diagnose ─▶ action
```

Env vars (separate, do not alias):

| Seam  | Model            | Vars |
| ----- | ---------------- | ---- |
| Read  | Gemini           | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| Agent | Freesolo (later) | `FREESOLO_AGENT_BASE_URL`, `FREESOLO_API_KEY`, `FREESOLO_AGENT_MODEL` |

**Do NOT point Freesolo at the Read seam.** A previous session miswired
Freesolo into `brain.py`'s dispatch; keep `FREESOLO_BASE_URL` blank in
`.env` so that path stays dormant. All Freesolo work targets `phoebe.py`.

Allocation summary: **Gemini = Read. Freesolo = Phoebe agent. Separate seams.**
