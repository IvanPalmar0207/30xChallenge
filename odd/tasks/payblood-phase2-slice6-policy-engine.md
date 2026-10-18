# PayBlood — Phase 2, Slice 6: Deterministic Invoice Policy Engine

Reference: `docs/implementation-contract.md` (unchanged invariants); slices 1-5 ODD specs.

## Specs

- **S1 — Scope**: deterministic backend engine that evaluates an invoice and
  produces `approved` (simulation only), `blocked` (mandatory rule
  violation), or `escalated` (human review / cannot decide safely). The AI
  never decides outside this engine. No payments, no budgets/POs (deferred).
- **S2 — Policy**: explicit, versioned, immutable organization policy.
  Creating a new policy deactivates the previous active one (one active per
  org); historical versions are never modified. `allowed_currencies=[]` means
  no currency restriction (documented). `max_amount` (hard cap → blocked),
  `escalation_threshold` (→ escalated), `require_due_date`,
  `require_description` (missing data → escalated). Coherence: when both
  limits are set, `escalation_threshold <= max_amount` (else 400).
- **S3 — Evaluation**: pure deterministic function, precedence
  `blocked → escalated → approved`; strict comparisons `amount > max_amount`
  blocks, `amount > escalation_threshold` escalates if not blocked before.
  No active policy → `escalated` (`no_active_policy`) — never approved
  without a valid applicable policy. Internal errors → 500, no partial
  decision, no state change, no internal details in the response.
- **S4 — Decision**: `PolicyDecision` persisted with result, reason_code,
  reason_detail, policy id/version, and an unambiguous `rules_snapshot` of
  the effective rules (later policy changes never alter recorded decisions).
  One decision per invoice (DB UniqueConstraint). The requester never chooses
  the outcome.
- **S5 — State machine**: `received → approved|blocked|escalated`. Evaluation
  requires `status == received` (else 409). Decision + status transition +
  `invoice_evaluated` audit event commit in one `transaction.atomic()`; any
  failure rolls back everything. No side effects on amount/currency/vendor/
  identity. Concurrency: `select_for_update()` on the invoice (PostgreSQL row
  lock) + the unique constraint as the universal backstop; SQLite
  concurrency is NOT claimed as validated.
- **S6 — Permissions**: policy reads for any active member; policy creation
  FINANCE_ADMIN only; evaluation request FINANCE_ADMIN/OPERATOR (the engine
  decides — OPERATOR never becomes a human approver); decision reads for any
  active member; uniform 404; org isolation on every query; no weakening of
  existing permissions.
- **S7 — Audit**: `invoice_evaluated` (result, reason_code, policy_version,
  decision_id — no secrets, no full body) and `policy_created` (version,
  is_active) events; transactional; append-only application-level.
- **S8 — Tests**: policy CRUD/validation/versioning; all evaluation outcomes
  + precedence + strict comparisons; no-policy → escalated; internal error →
  500 no effects; cross-org; roles; repeated evaluation → 409; decision
  persistence + snapshot; invoice unchanged; audit + rollback; malformed
  UUIDs; full-suite regression.
- **S9 — Docs**: README (policy engine, rules, precedence, snapshot,
  limitations), contract changelog row, ODD spec (no mirror).

## Tasks

| ID | Specs | Description | Status |
| --- | --- | --- | --- |
| T1 | S2,S4,S5,S7 | `Policy` + `PolicyDecision` models, `Invoice.Status` extended, `INVOICE_EVALUATED`/`POLICY_CREATED` actions, migration `0006` | done |
| T2 | S2,S3,S4,S5,S6 | Serializers + `evaluate_invoice` engine + `_policy_snapshot` + views (policies, evaluate, decision) + routes + read-only admin | done |
| T3 | S8 | `tests_policy.py` (34 tests) | done |
| T4 | S9 | README + contract changelog + ODD log | done |
| T5 | S9 | Validation: check, makemigrations --check, full suite isolated, diff + secret review, report | done |

## Log

- L1: user request verbatim (abbreviated): "Slice 6: Deterministic Invoice
  Policy Engine … construir un motor determinista … approved/blocked/escalated
  … La IA no puede tomar decisiones financieras por fuera de este motor …
  No aprobar automáticamente si no existe una política válida y aplicable …
  No confiar en campos de decisión enviados por el cliente o por la IA …
  Registrar decisiones y motivos mediante auditoría …" (plan turn).
- L2 (user-approved conditions): (1) precedence `blocked → escalated →
  approved`; strict comparisons `amount > max_amount` blocks, `amount >
  escalation_threshold` escalates if not blocked before; validate coherence
  between both limits when both configured. (2) explicit semantics for
  optional rules and `allowed_currencies=[]`; no ambiguous config may
  produce an unsafe approval. (3) atomicity of decision + Invoice.Status
  transition + AuditEvent; any failure rolls back everything. (4) protect
  against concurrency and duplicate decisions: `select_for_update()` when
  supported + the DB unique constraint; do not claim SQLite concurrency is
  validated if the test needs PostgreSQL-specific guarantees. (5) keep an
  unambiguous snapshot of the applied policy (id, version, effective rules);
  historical versions are never modified. (6) internal errors → 500 with no
  partial decision or state change; no internal details in the response.
  (7) preserve org isolation, permissions, safe audit, and all previously
  agreed Git constraints.
- L3 (recovery turn): user asked to inspect the repo first, preserve all
  pending Slice 5 work, complete only what Slice 6 was missing, run the full
  suite in an isolated test database, and report without staging/committing.
  Findings: T1-T4 code already existed uncommitted (models, migration 0006,
  serializers, engine, views, routes, admin, 34 tests). Two defects were
  fixed: (1) `InvoiceDecisionView` answered 404 for every decision read because
  the generic `RetrieveAPIView` lookup used the decision's own `pk` instead of
  `invoice_id` — fixed with `lookup_field = "invoice_id"` +
  `lookup_url_kwarg = "pk"`; (2) `test_evaluate_does_not_change_invoice_business_data`
  compared an in-memory string amount against the persisted Decimal — fixed by
  refreshing the invoice before capturing the baseline (removed leftover DEBUG
  prints too). Docs (README policy engine section, contract changelog row) were
  missing and added. Final: 210/210 tests, check/makemigrations --check/
  git diff --check clean, no secrets in diff.
