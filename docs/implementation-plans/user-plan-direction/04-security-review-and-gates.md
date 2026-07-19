# PD-D — Security Review and Gates

The user asked for security measures "against all aspects, prompt
injections first." This phase is a checklist walk: every threat below
must end the session either **verified** (named test or gate) or
**accepted** (written down as such). No silent skips.

## Threat model

| # | Threat | Mitigation | Verified by |
| --- | --- | --- | --- |
| T1 | **Prompt injection**: pasted plan instructs the model to ignore rules, inflate scope, or bypass constraints | Labeled data-not-instructions block; hedge sentence names the block; deterministic disposal is the real defense — `_check_against_constraints`, `validate_syllabus_units`, bounded repair (≤2, typed `reason_code`), planner validation, approval gate. The field is never control-plane state. | PD-B §5a injection test; existing constraint/validator suites |
| T2 | **Fabricated evidence**: injected text steers the model to cite nonexistent/expired claims or fake company-specific justification | Claim registry built from the deterministically curated KEPT set (`app/cycle.py:557-571`); unknown/expired ids are typed violations | PD-B §5b test; existing `validate_syllabus_units` suite |
| T3 | **Leak to calendar surface**: injected text steers module titles → task titles → Google event summaries (post calendar-event-titles) | Titles come only from the **approved** plan version — the user reviews every title at the approval gate; writes go to the user's own dedicated calendar; adapter-level title sanitization per that plan | Approval-gate suite (existing); calendar-event-titles plan T-A sanitization |
| T4 | **PII / data handling**: plan text may contain personal detail | Same posture as `resume_text`: profile record only, deleted with profile, call log stores hashes and counts only (axiom 22), never training | Spec paragraph (PD-A §1); call-log posture is structural — confirm no test/debug sink logs the raw field (`grep -rn "plan_direction" backend/src` at the end of the session and account for every hit) |
| T5 | **Resource abuse / cost**: oversized paste inflates tokens or storage | Server-side cap 4,000 chars in the contract (~≤1.5k tokens); `STRATEGIST_CONFIG` budgets unchanged; onboard sits behind the existing authenticated session | PD-A bounds tests; contract is the enforcement point (frontend `maxLength` is UX only) |
| T6 | **Control-character smuggling**: NUL/escape sequences in the paste (log injection, downstream parser confusion) | Contract validator rejects C0 except `\n\r\t` with a typed violation | PD-A validator tests + invalid fixture. Accepted risk, written here deliberately: zero-width/bidi Unicode is **not** blocked — the field never becomes control-plane state or a rendered-HTML sink, and over-blocking breaks legitimate paste |
| T7 | **XSS / rendering**: field echoed into the SPA | Value appears only as a controlled `<textarea>` value; React escapes by default; no `dangerouslySetInnerHTML` | Review item: `grep -rn "dangerouslySetInnerHTML" frontend/src` stays clean; PD-C §5 |
| T8 | **Trust boundary / write paths**: field injected via an unintended endpoint or another user | Single write path `POST /api/onboard` (server overwrites `user_id`, `routes_cycle.py:14`); no new endpoints; field is per-user profile data, never composed into another user's prompt | PD-C §1; route inventory unchanged |
| T9 | **Scope creep into other prompts**: field silently reaches Planner/Reflection/Explanation later | Normative Prompt Exposure table + exclusion-set assertion keep code and spec in lockstep | `tests/contracts/test_user_profile.py` exclusion assert (PD-B §1); spec table (PD-A §1) |

## Claim sweep

Before gates, grep and reconcile every claim the docs/code make about
the field:

- `grep -rn "plan_direction" backend/src backend/tests docs frontend/src`
  — every hit is either implemented behavior or normative spec text;
  no aspirational claims.
- The spec's exclusion-set sentence, the adapter frozenset, and the
  contract test must state the same three-element set.
- Docstrings must not overclaim (e.g., never say "sanitized" — the
  contract *rejects*, it does not rewrite).

## Gates (all green before the commit)

From `backend/`:

```bash
uv run make check        # full: tests, lint, typecheck, boundaries
```

From `frontend/`:

```bash
npm run typecheck && npm run lint && npm test && npm run build
```

Plus:

- `make schemas` produced exactly one changed file
  (`schemas/user_profile.schema.json`) — check the diff.
- `graphify update .` after code changes.

## Honest-reporting requirements

- If any existing test fails for reasons outside this plan's scope,
  stop and report — do not fix drive-by.
- If the eval harness pins prompt content (PD-B §6), name the updated
  test in the session summary.
- State plainly in the commit message that replans are unaffected by
  design.
