import { Component, signal } from '@angular/core';

import { Sound } from '../../shared/sound';

/**
 * Interactive visual demo of the invoice processing flow.
 *
 * The records below are static examples for the demo only. The walkthrough
 * illustrates the STAGES and the DECISION ORDER of the engine; it never
 * calculates or decides anything — the deterministic engine runs in the
 * backend and remains the sole authority (footer note in the template).
 */

type Decision = 'approved' | 'blocked' | 'escalated';

interface DemoInvoice {
  id: number;
  number: string;
  vendor: string;
  amount: string;
  currency: string;
  decision: Decision;
  reason: string;
  stage: number; // 0 = ingested, 1 = extracted, 2 = evaluated, 3 = reviewed
}

const STAGES = ['Ingested', 'Extracted', 'Evaluated', 'Reviewed'] as const;

const DECISION_GLYPH: Record<Decision, string> = {
  approved: '✓',
  blocked: '✕',
  escalated: '▲',
};

const DEMO: DemoInvoice[] = [
  {
    id: 1,
    number: 'INV-2201',
    vendor: 'Northwind Works',
    amount: '4,280.00',
    currency: 'USD',
    decision: 'approved',
    reason: 'policy_ok — complies with the active policy',
    stage: 0,
  },
  {
    id: 2,
    number: 'INV-2203',
    vendor: 'Volta Energy',
    amount: '12,900.00',
    currency: 'USD',
    decision: 'blocked',
    reason: 'amount_exceeds_max — hard cap violated',
    stage: 0,
  },
  {
    id: 3,
    number: 'INV-2204',
    vendor: 'Meridian Logistics',
    amount: '6,540.00',
    currency: 'EUR',
    decision: 'blocked',
    reason: 'currency_not_allowed',
    stage: 0,
  },
  {
    id: 4,
    number: 'INV-2207',
    vendor: 'Trustline Software',
    amount: '3,175.00',
    currency: 'USD',
    decision: 'escalated',
    reason: 'amount_exceeds_escalation_threshold — human review',
    stage: 0,
  },
];

@Component({
  selector: 'pb-invoice-pipeline',
  templateUrl: './invoice-pipeline.html',
  styles: `
    .pipeline {
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-l);
      background: var(--pb-surface);
      box-shadow: var(--pb-shadow-card);
      overflow: hidden;
    }

    .pipeline__bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--pb-space-4);
      padding: var(--pb-space-4) var(--pb-space-5);
      border-bottom: 1px solid var(--pb-line);
      background: var(--pb-surface-2);
    }

    .pipeline__bar p {
      color: var(--pb-muted);
      font-size: 0.8125rem;
      margin: 0;
    }

    .pipeline__controls {
      display: flex;
      align-items: center;
      gap: var(--pb-space-2);
    }

    .pipeline__sound {
      display: inline-flex;
      align-items: center;
      gap: var(--pb-space-2);
      padding: 0.4375rem 0.75rem;
      border: 1px solid var(--pb-line-strong);
      border-radius: var(--pb-radius-pill);
      background: transparent;
      color: var(--pb-ink-soft);
      font-size: 0.8125rem;
      font-weight: 600;
      transition: border-color var(--pb-dur) var(--pb-ease),
        color var(--pb-dur) var(--pb-ease);
    }

    .pipeline__sound[aria-pressed='true'] {
      border-color: var(--pb-brand);
      color: var(--pb-brand-text);
      background: var(--pb-brand-soft);
    }

    .pipeline__rows {
      display: grid;
    }

    .pipeline__row {
      display: grid;
      grid-template-columns: 1.4fr 1fr 1fr auto auto;
      align-items: center;
      gap: var(--pb-space-4);
      padding: var(--pb-space-3) var(--pb-space-5);
      border-bottom: 1px solid var(--pb-line);
      transition: background var(--pb-dur) var(--pb-ease);
    }

    .pipeline__row:last-child {
      border-bottom: 0;
    }

    .pipeline__row.is-active {
      background: color-mix(in srgb, var(--pb-brand-soft) 60%, transparent);
    }

    .pipeline__meta {
      display: flex;
      flex-direction: column;
      gap: 0.125rem;
    }

    .pipeline__num {
      font-family: var(--pb-font-mono);
      font-size: 0.875rem;
      font-weight: 600;
    }

    .pipeline__vendor {
      color: var(--pb-muted);
      font-size: 0.8125rem;
    }

    .pipeline__amount {
      font-family: var(--pb-font-mono);
      font-variant-numeric: tabular-nums;
      font-size: 0.9375rem;
    }

    .pipeline__stage {
      display: inline-flex;
      align-items: center;
      gap: 0.375rem;
      font-size: 0.8125rem;
      color: var(--pb-ink-soft);
      min-width: 0;
    }

    .pipeline__prog {
      width: 56px;
      height: 4px;
      border-radius: var(--pb-radius-pill);
      background: var(--pb-line);
      overflow: hidden;
    }

    .pipeline__prog-fill {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: var(--pb-brand-strong);
      transition: width var(--pb-dur-slow) var(--pb-ease);
    }

    .pipeline__dot {
      width: 8px;
      height: 8px;
      border-radius: var(--pb-radius-pill);
      background: var(--pb-line-strong);
      transition: background var(--pb-dur) var(--pb-ease);
    }

    .pipeline__dot.is-live {
      background: var(--pb-brand);
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 0.375rem;
      padding: 0.25rem 0.625rem;
      border-radius: var(--pb-radius-pill);
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .badge__glyph {
      font-size: 0.75rem;
      line-height: 1;
    }

    .badge--approved {
      color: var(--pb-approved);
      background: var(--pb-approved-bg);
    }

    .badge--blocked {
      color: var(--pb-blocked);
      background: var(--pb-blocked-bg);
    }

    .badge--escalated {
      color: var(--pb-escalated);
      background: var(--pb-escalated-bg);
    }

    .badge--empty {
      color: var(--pb-muted);
      background: transparent;
      border: 1px dashed var(--pb-line-strong);
    }

    .pipeline__foot {
      padding: var(--pb-space-4) var(--pb-space-5);
      font-size: 0.8125rem;
      color: var(--pb-muted);
      border-top: 1px solid var(--pb-line);
      display: flex;
      gap: var(--pb-space-3);
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
    }

    @media (max-width: 760px) {
      .pipeline__row {
        grid-template-columns: 1fr 1fr;
        row-gap: var(--pb-space-2);
      }
      .pipeline__stage,
      .pipeline__decision {
        grid-column: span 1;
      }
    }
  `,
})
export class InvoicePipeline {
  readonly rows = signal<DemoInvoice[]>([]);
  readonly activeId = signal<number>(1);
  readonly soundOn = signal(false);
  protected readonly STAGES = STAGES;

  constructor(private readonly sound: Sound) {
    this.rows.set(
      DEMO.map((row, index) => ({ ...row, stage: index === 0 ? 1 : 0 })),
    );
  }

  protected glyph(decision: Decision): string {
    return DECISION_GLYPH[decision];
  }

  protected progressOf(row: DemoInvoice): number {
    const max = row.decision === 'escalated' ? 3 : 2;
    return Math.round((row.stage / max) * 100);
  }

  activeRow(): DemoInvoice {
    const row = this.rows().find((r) => r.id === this.activeId());
    return row ?? this.rows()[0];
  }

  advance(): void {
    const row = this.activeRow();
    const max = row.decision === 'escalated' ? 3 : 2; // reviewed only when escalated
    const next = Math.min(row.stage + 1, max);
    this.rows.update((all) =>
      all.map((r) => (r.id === row.id ? { ...r, stage: next } : r)),
    );
    if (next > row.stage) {
      if (next >= 2) {
        this.sound.resolve();
      } else {
        this.sound.tick();
      }
    }
  }

  select(id: number): void {
    this.activeId.set(id);
  }

  stageLabel(stage: number): string {
    return STAGES[Math.min(stage, STAGES.length - 1)];
  }

  toggleSound(): void {
    const next = !this.soundOn();
    this.soundOn.set(next);
    this.sound.setEnabled(next);
  }
}