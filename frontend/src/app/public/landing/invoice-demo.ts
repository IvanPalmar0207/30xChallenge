import { animate, style, transition, trigger } from '@angular/animations';
import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Sound } from '../../shared/sound';
import {
  ConditionResult,
  DemoDecision,
  DemoInvoice,
  DemoOutcome,
  DemoPolicy,
} from './types';

/**
 * Invoice evaluation lab — the landing's main interactive section.
 *
 * Everything here is a LOCAL, deterministic simulation of the engine's
 * documented precedence over example records. It never calls the backend and
 * is labelled "demo" in the UI. No AI is simulated; no payment is simulated.
 */

const POLICY: DemoPolicy = {
  label: 'Example policy · v3 (demo)',
  allowedCurrencies: ['USD', 'EUR'],
  maxAmount: 10_000,
  escalationThreshold: 5_000,
  requireDueDate: true,
};

const INVOICES: DemoInvoice[] = [
  {
    id: 'demo-a',
    vendor: 'Volta Energy',
    number: 'INV-2203',
    amount: 12_900,
    currency: 'USD',
    dueDate: '2026-11-30',
    description: 'Energy services',
  },
  {
    id: 'demo-b',
    vendor: 'Meridian Logistics',
    number: 'INV-2204',
    amount: 6_540,
    currency: 'EUR',
    dueDate: null,
    description: 'Freight forwarding',
  },
  {
    id: 'demo-c',
    vendor: 'Northwind Works',
    number: 'INV-2201',
    amount: 4_280,
    currency: 'USD',
    dueDate: '2026-11-15',
    description: 'Consulting services',
  },
];

/** Local replica of the engine's documented precedence, demo-scoped. */
function evaluateDemo(invoice: DemoInvoice, policy: DemoPolicy): DemoOutcome {
  const conditions: ConditionResult[] = [
    {
      key: 'currency',
      label: 'Currency allowed',
      detail: `${invoice.currency} ∈ {${policy.allowedCurrencies.join(', ')}}`,
      passed: policy.allowedCurrencies.includes(invoice.currency),
    },
    {
      key: 'max',
      label: 'Amount ≤ max_amount',
      detail: `${formatMoney(invoice.amount)} ≤ ${formatMoney(policy.maxAmount)} (hard cap)`,
      passed: invoice.amount <= policy.maxAmount,
    },
    {
      key: 'threshold',
      label: 'Amount ≤ escalation_threshold',
      detail: `${formatMoney(invoice.amount)} ≤ ${formatMoney(policy.escalationThreshold)}`,
      passed: invoice.amount <= policy.escalationThreshold,
    },
    {
      key: 'due',
      label: 'Due date present',
      detail: policy.requireDueDate ? 'Policy requires due_date' : 'Not required',
      passed: !policy.requireDueDate || invoice.dueDate !== null,
    },
  ];

  const currency = conditions.find((c) => c.key === 'currency')!;
  const max = conditions.find((c) => c.key === 'max')!;
  const threshold = conditions.find((c) => c.key === 'threshold')!;
  const due = conditions.find((c) => c.key === 'due')!;

  // Precedence: blocked → escalated → approved (mirrors the backend).
  if (!currency.passed) {
    return {
      decision: 'blocked',
      reasonCode: 'currency_not_allowed',
      reasonDetail: `Currency ${invoice.currency} is not allowed by the active policy.`,
      conditions,
    };
  }
  if (!max.passed) {
    return {
      decision: 'blocked',
      reasonCode: 'amount_exceeds_max',
      reasonDetail: `Amount ${formatMoney(invoice.amount)} exceeds the policy maximum.`,
      conditions,
    };
  }
  if (!threshold.passed || !due.passed) {
    return {
      decision: 'escalated',
      reasonCode: !threshold.passed
        ? 'amount_exceeds_escalation_threshold'
        : 'due_date_missing',
      reasonDetail: !threshold.passed
        ? 'Amount above the escalation threshold — human review required.'
        : 'The policy requires a due date.',
      conditions,
    };
  }
  return {
    decision: 'approved',
    reasonCode: 'policy_ok',
    reasonDetail: 'The invoice complies with the active policy.',
    conditions,
  };
}

function formatMoney(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
}

interface DemoAuditRow {
  action: string;
  target: string;
  note: string;
}

@Component({
  selector: 'pb-invoice-demo',
  imports: [CommonModule, FormsModule],
  animations: [
    trigger('fadeIn', [
      transition(':enter', [
        style({ opacity: 0, transform: 'translateY(8px)' }),
        animate('260ms cubic-bezier(0.2,0.7,0.2,1)', style({ opacity: 1, transform: 'none' })),
      ]),
    ]),
    trigger('staggerItem', [
      transition(':enter', [
        style({ opacity: 0, transform: 'translateX(-6px)' }),
        animate('220ms cubic-bezier(0.2,0.7,0.2,1)', style({ opacity: 1, transform: 'none' })),
      ]),
    ]),
  ],
  template: `
    <section class="lab" aria-label="Invoice evaluation demo">
      <header class="lab__bar">
        <span class="lab__tag">Demo · local simulation</span>
        <span class="lab__policy pb-mono">{{ policy.label }}</span>
      </header>

      <div class="lab__grid">
        <div class="lab__input">
          <h3 class="lab__sub">1 · Pick an invoice</h3>
          <div class="invoice-pick" role="listbox" aria-label="Example invoices">
            @for (invoice of invoices(); track invoice.id) {
              <button
                type="button"
                class="invoice-pick__item"
                [class.is-active]="selected().id === invoice.id"
                role="option"
                [attr.aria-selected]="selected().id === invoice.id"
                (click)="selectInvoice(invoice.id)"
              >
                <span class="invoice-pick__name">{{ invoice.vendor }}</span>
                <span class="pb-mono invoice-pick__num">{{ invoice.number }}</span>
              </button>
            }
          </div>

          <label class="field">
            <span class="field__label">Amount</span>
            <input
              type="range"
              min="1000"
              max="14000"
              step="100"
              [value]="selected().amount"
              (input)="setAmount($event)"
            />
            <span class="pb-mono field__value">{{ selected().amount | number }}</span>
          </label>

          <label class="field">
            <span class="field__label">Currency</span>
            <select [value]="selected().currency" (change)="setCurrency($event)">
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="COP">COP</option>
            </select>
            <span class="field__hint">COP is not allowed by the demo policy.</span>
          </label>

          <dl class="fields-static">
            <div><dt>Invoice</dt><dd class="pb-mono">{{ selected().number }}</dd></div>
            <div><dt>Due date</dt><dd class="pb-mono">{{ selected().dueDate ?? 'missing' }}</dd></div>
            <div><dt>Description</dt><dd>{{ selected().description }}</dd></div>
          </dl>
        </div>

        <div class="lab__rules">
          <h3 class="lab__sub">2 · Rules that apply</h3>
          <ul class="conditions">
            @for (condition of conditions(); track condition.key) {
              <li class="condition" [class.is-pass]="condition.passed" [class.is-fail]="!condition.passed" @staggerItem>
                <span class="condition__mark" aria-hidden="true">
                  {{ condition.passed ? '✓' : '✕' }}
                </span>
                <span class="condition__label">{{ condition.label }}</span>
                <span class="pb-mono condition__detail">{{ condition.detail }}</span>
              </li>
            }
          </ul>

          <p class="lab__precedence">
            Precedence everywhere: <strong>blocked → escalated → approved</strong>. The
            first failing rule decides; nothing is approved without an active policy.
          </p>

          <div class="lab__actions">
            <button
              type="button"
              class="pb-btn pb-btn--primary lab__run"
              (click)="evaluate()"
              [disabled]="evaluating()"
            >
              @if (evaluating()) {
                <span class="orb" aria-hidden="true"><i></i><i></i><i></i></span>
                The engine is evaluating…
              } @else {
                Evaluate (demo)
              }
            </button>
            <button type="button" class="pb-btn pb-btn--ghost" (click)="reset()">
              Reset scenario
            </button>
          </div>
        </div>

        <div class="lab__outcome" [attr.aria-live]="'polite'">
          <h3 class="lab__sub">3 · Outcome</h3>

          @if (evaluating()) {
            <div class="skeleton" aria-hidden="true">
              <span class="skeleton__line" style="width: 34%"></span>
              <span class="skeleton__line" style="width: 72%"></span>
              <span class="skeleton__line" style="width: 100%"></span>
              <span class="skeleton__line" style="width: 58%"></span>
            </div>
          } @else if (outcome()) {
            <div
              @fadeIn
              class="result"
              [class.result--approved]="outcome()!.decision === 'approved'"
              [class.result--blocked]="outcome()!.decision === 'blocked'"
              [class.result--escalated]="outcome()!.decision === 'escalated'"
            >
              <p class="result__decision">
                <span class="result__glyph" aria-hidden="true">{{ glyph(outcome()!.decision) }}</span>
                {{ outcome()!.decision }}
              </p>
              <p class="pb-mono result__code">{{ outcome()!.reasonCode }}</p>
              <p class="result__detail">{{ outcome()!.reasonDetail }}</p>
            </div>

            <div class="trace">
              <h4 class="trace__title">Audit trail (demo)</h4>
              <ol class="trace__items">
                @for (row of auditTrail(); track $index) {
                  <li>
                    <span class="pb-mono trace__action">{{ row.action }}</span>
                    <span class="pb-mono trace__target">{{ row.target }}</span>
                    <span class="trace__note">{{ row.note }}</span>
                  </li>
                }
              </ol>
            </div>
          } @else {
            <p class="lab__idle">
              No evaluation yet. Adjust the amount or currency, then run the
              evaluation to see which rule decides.
            </p>
          }
        </div>
      </div>

      <p class="lab__foot">
        Local simulation with example data — this playground does not call the
        backend and creates no records. The authoritative engine runs server-side.
      </p>
    </section>
  `,
  styles: `
    .lab {
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-l);
      background: var(--pb-surface);
      box-shadow: var(--pb-shadow-card);
      overflow: hidden;
    }

    .lab__bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--pb-space-3);
      padding: var(--pb-space-3) var(--pb-space-4);
      border-bottom: 1px solid var(--pb-line);
      flex-wrap: wrap;
    }

    .lab__tag {
      font-family: var(--pb-font-mono);
      font-size: 0.625rem;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--pb-highlight);
    }

    .lab__policy {
      font-size: 0.6875rem;
      color: var(--pb-muted);
    }

    .lab__grid {
      display: grid;
      grid-template-columns: 7fr 5fr;
      gap: 0;
    }

    .lab__input,
    .lab__rules,
    .lab__outcome {
      padding: var(--pb-space-5);
    }

    .lab__input,
    .lab__rules {
      border-bottom: 1px solid var(--pb-line);
    }

    .lab__outcome {
      grid-column: 1 / -1;
    }

    .lab__sub {
      font-size: 0.875rem;
      letter-spacing: -0.01em;
      margin-bottom: var(--pb-space-3);
    }

    .invoice-pick {
      display: grid;
      gap: var(--pb-space-2);
      margin-bottom: var(--pb-space-4);
    }

    .invoice-pick__item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--pb-space-3);
      padding: var(--pb-space-2) var(--pb-space-3);
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-m);
      background: transparent;
      color: var(--pb-ink);
      text-align: left;
      font-size: var(--pb-text-sm);
      transition: border-color var(--pb-dur) var(--pb-ease),
        background var(--pb-dur) var(--pb-ease);
    }

    .invoice-pick__item:hover {
      border-color: var(--pb-line-strong);
    }

    .invoice-pick__item.is-active {
      border-color: var(--pb-brand);
      background: var(--pb-brand-soft);
    }

    .invoice-pick__name {
      font-weight: 600;
    }

    .invoice-pick__num {
      color: var(--pb-muted);
      font-size: 0.75rem;
    }

    .field {
      display: grid;
      grid-template-columns: 5.5rem 1fr auto;
      align-items: center;
      gap: var(--pb-space-3);
      margin-bottom: var(--pb-space-3);
    }

    .field__label {
      color: var(--pb-ink-soft);
      font-size: var(--pb-text-sm);
    }

    input[type='range'] {
      width: 100%;
      accent-color: var(--pb-brand-strong);
    }

    select {
      padding: 0.375rem 0.5rem;
      border: 1px solid var(--pb-line-strong);
      border-radius: var(--pb-radius-m);
      background: var(--pb-surface);
      color: var(--pb-ink);
      font-size: var(--pb-text-sm);
    }

    .field__value {
      min-width: 3.5rem;
      text-align: right;
    }

    .field__hint {
      grid-column: 2 / -1;
      color: var(--pb-muted);
      font-size: var(--pb-text-xs);
    }

    .fields-static {
      margin: var(--pb-space-4) 0 0;
      padding: 0;
    }

    .fields-static div {
      display: grid;
      grid-template-columns: 6rem 1fr;
      padding: var(--pb-space-2) 0;
      border-bottom: 1px solid var(--pb-line);
      font-size: var(--pb-text-sm);
    }

    .fields-static dt {
      color: var(--pb-muted);
    }

    .fields-static dd {
      margin: 0;
    }

    .conditions {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: var(--pb-space-1);
    }

    .condition {
      display: grid;
      grid-template-columns: 1.6rem 1fr auto;
      align-items: center;
      gap: var(--pb-space-2);
      padding: var(--pb-space-2) var(--pb-space-3);
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-m);
      font-size: var(--pb-text-sm);
      transition: border-color var(--pb-dur) var(--pb-ease);
    }

    .condition__mark {
      width: 20px;
      height: 20px;
      border-radius: var(--pb-radius-pill);
      display: grid;
      place-items: center;
      font-size: 0.75rem;
      font-weight: 800;
    }

    .condition.is-pass .condition__mark {
      background: var(--pb-approved-bg);
      color: var(--pb-approved);
    }

    .condition.is-fail .condition__mark {
      background: var(--pb-blocked-bg);
      color: var(--pb-blocked);
    }

    .condition__label {
      font-weight: 600;
    }

    .condition__detail {
      color: var(--pb-muted);
      font-size: 0.6875rem;
    }

    .lab__precedence {
      margin-top: var(--pb-space-3);
      color: var(--pb-muted);
      font-size: var(--pb-text-sm);
    }

    .lab__precedence strong {
      color: var(--pb-ink);
    }

    .lab__actions {
      margin-top: var(--pb-space-4);
      display: grid;
      grid-template-columns: 1fr auto;
      gap: var(--pb-space-2);
    }

    @media (max-width: 560px) {
      .lab__actions {
        grid-template-columns: 1fr;
      }
    }

    .lab__idle {
      color: var(--pb-muted);
      font-size: var(--pb-text-sm);
      max-width: 34rem;
    }

    .result {
      border: 1px solid var(--pb-line-strong);
      border-left-width: 4px;
      border-radius: var(--pb-radius-m);
      padding: var(--pb-space-4);
      display: grid;
      gap: var(--pb-space-1);
    }

    .result--approved { border-left-color: var(--pb-approved); }
    .result--blocked { border-left-color: var(--pb-blocked); }
    .result--escalated { border-left-color: var(--pb-escalated); }

    .result__decision {
      display: inline-flex;
      align-items: center;
      gap: var(--pb-space-2);
      font-family: var(--pb-font-display);
      font-weight: 800;
      font-size: 1.375rem;
      text-transform: capitalize;
    }

    .result--approved .result__decision { color: var(--pb-approved); }
    .result--blocked .result__decision { color: var(--pb-blocked); }
    .result--escalated .result__decision { color: var(--pb-escalated); }

    .result__glyph {
      font-size: 1.125rem;
    }

    .result__code {
      color: var(--pb-muted);
    }

    .result__detail {
      color: var(--pb-ink-soft);
      font-size: var(--pb-text-sm);
    }

    .trace {
      margin-top: var(--pb-space-4);
      border: 1px dashed var(--pb-line-strong);
      border-radius: var(--pb-radius-m);
      padding: var(--pb-space-3) var(--pb-space-4);
    }

    .trace__title {
      font-family: var(--pb-font-mono);
      font-size: 0.625rem;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--pb-muted);
      margin-bottom: var(--pb-space-2);
    }

    .trace__items {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: var(--pb-space-1);
    }

    .trace__items li {
      display: grid;
      grid-template-columns: 9rem 9rem 1fr;
      gap: var(--pb-space-2);
      font-size: var(--pb-text-xs);
      padding: var(--pb-space-1) 0;
      border-bottom: 1px solid var(--pb-line);
    }

    .trace__action {
      color: var(--pb-brand-strong);
    }

    .trace__target {
      color: var(--pb-muted);
    }

    .trace__note {
      color: var(--pb-ink-soft);
    }

    .orb {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.orb i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--pb-accent);
  opacity: 0.35;
  animation: pb-orb 1.1s ease-in-out infinite;
}

.orb i:nth-child(2) { animation-delay: 0.18s; }
.orb i:nth-child(3) { animation-delay: 0.36s; }

@keyframes pb-orb {
  0%, 60%, 100% { opacity: 0.35; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-2px); }
}

.skeleton {
  display: grid;
  gap: var(--pb-space-2);
  padding: var(--pb-space-4);
  border: 1px solid var(--pb-line);
  border-radius: var(--pb-radius-m);
}

.skeleton__line {
  height: 12px;
  border-radius: var(--pb-radius-s);
  background: linear-gradient(90deg, var(--pb-line) 25%, color-mix(in srgb, var(--pb-line) 40%, transparent) 50%, var(--pb-line) 75%);
  background-size: 200% 100%;
  animation: pb-shimmer 1.3s ease-in-out infinite;
}

@keyframes pb-shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

.lab__foot {
      padding: var(--pb-space-3) var(--pb-space-4);
      border-top: 1px solid var(--pb-line);
      color: var(--pb-muted);
      font-size: var(--pb-text-xs);
    }

    @media (max-width: 900px) {
      .lab__grid {
        grid-template-columns: 1fr;
      }

      .lab__outcome {
        grid-column: 1;
      }
    }

    @media (max-width: 560px) {
      .trace__items li {
        grid-template-columns: 1fr;
        gap: 0;
      }
    }
  `,
})
export class InvoiceDemo {
  protected readonly policy = POLICY;
  protected readonly invoices = signal(INVOICES);
  protected readonly selected = signal<DemoInvoice>({ ...INVOICES[2] });
  protected readonly conditions = signal<ConditionResult[]>([]);
  protected readonly outcome = signal<DemoOutcome | null>(null);
  protected readonly auditTrail = signal<DemoAuditRow[]>([]);
  protected readonly evaluating = signal(false);
  private timers: number[] = [];

  constructor(private readonly sound: Sound) {}

  protected glyph(decision: DemoDecision): string {
    return decision === 'approved' ? '✓' : decision === 'blocked' ? '✕' : '▲';
  }

  protected selectInvoice(id: string): void {
    const found = this.invoices().find((i) => i.id === id);
    if (found) {
      this.selected.set({ ...found });
      this.outcome.set(null);
      this.auditTrail.set([]);
    }
  }

  protected setAmount(event: Event): void {
    const value = Number((event.target as HTMLInputElement).value);
    this.selected.update((invoice) => ({ ...invoice, amount: value }));
    this.outcome.set(null);
    this.auditTrail.set([]);
  }

  protected setCurrency(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.selected.update((invoice) => ({ ...invoice, currency: value }));
    this.outcome.set(null);
    this.auditTrail.set([]);
  }

  protected reset(): void {
    this.timers.forEach((t) => window.clearTimeout(t));
    this.timers = [];
    this.selected.set({ ...INVOICES[2] });
    this.conditions.set([]);
    this.outcome.set(null);
    this.auditTrail.set([]);
    this.evaluating.set(false);
  }

  protected evaluate(): void {
    if (this.evaluating()) return;
    this.evaluating.set(true);
    this.conditions.set(evaluateDemo(this.selected(), this.policy).conditions);
    this.timers.push(
      window.setTimeout(() => {
        const result = evaluateDemo(this.selected(), this.policy);
        this.outcome.set(result);
        this.auditTrail.set([
          {
            action: 'invoice_evaluated',
            target: this.selected().number,
            note: `${result.decision} · ${result.reasonCode}`,
          },
          {
            action: 'audit_event',
            target: 'append-only',
            note: 'actor + organization + safe metadata (demo)',
          },
        ]);
        this.evaluating.set(false);
        if (result.decision === 'approved') {
          this.sound.resolve();
        } else {
          this.sound.tick();
        }
      }, 650),
    );
  }

  ngOnDestroy(): void {
    this.timers.forEach((t) => window.clearTimeout(t));
  }
}