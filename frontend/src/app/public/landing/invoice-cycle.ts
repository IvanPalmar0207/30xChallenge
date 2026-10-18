import { Component, signal } from '@angular/core';

/**
 * The invoice cycle — Option A: an interactive, data-driven walkthrough
 * instead of a decorative timeline. Selecting a stage updates the detail
 * panel with real information about that part of the flow. Example data is
 * labelled; planned capabilities are marked "planned".
 */

interface CycleField {
  key: string;
  value: string;
}

interface CycleRule {
  label: string;
  detail: string;
  passed: boolean;
}

interface CycleDetail {
  heading: string;
  badge?: { text: string; tone: 'approved' | 'escalated' | 'blocked' | 'planned' };
  intro: string;
  fields?: CycleField[];
  rules?: CycleRule[];
  note: string;
}

interface CycleStage {
  id: string;
  number: string;
  label: string;
  teaser: string;
  planned?: boolean;
  detail: CycleDetail;
}

const STAGES: CycleStage[] = [
  {
    id: 'receive',
    number: '01',
    label: 'Receive',
    teaser: 'What enters the organization.',
    detail: {
      heading: 'What enters — example invoice',
      badge: { text: 'received', tone: 'approved' },
      intro: 'The invoice is registered with a server-assigned status. No decision is made at this stage.',
      fields: [
        { key: 'vendor', value: 'Northwind Works' },
        { key: 'invoice', value: 'INV-2201' },
        { key: 'issue', value: '2026-10-01' },
        { key: 'due', value: '2026-11-15' },
        { key: 'amount', value: 'USD 4,280.00' },
        { key: 'status', value: 'received · server-assigned' },
      ],
      note: 'These fields are the minimum data an invoice carries in the current API.',
    },
  },
  {
    id: 'extract',
    number: '02',
    label: 'Extract',
    teaser: 'Fields structured for evaluation.',
    planned: true,
    detail: {
      heading: 'Structured fields',
      badge: { text: 'planned', tone: 'planned' },
      intro: 'Automated extraction is NOT implemented yet. This stage shows the field contract a future extractor would fill.',
      fields: [
        { key: 'vendor', value: 'resolved by extraction' },
        { key: 'invoice number', value: 'normalized: strip + uppercase' },
        { key: 'dates', value: 'issue_date, due_date' },
        { key: 'amount', value: 'Decimal — never float' },
        { key: 'currency', value: 'ISO 4217, curated list' },
      ],
      note: 'Until extraction exists, invoices are registered manually through the API.',
    },
  },
  {
    id: 'evaluate',
    number: '03',
    label: 'Evaluate',
    teaser: 'The policy decides, deterministically.',
    detail: {
      heading: 'Rules applied to the example',
      badge: { text: 'approved', tone: 'approved' },
      intro: 'The active policy is evaluated in fixed precedence: blocked → escalated → approved.',
      rules: [
        { label: 'Currency allowed', detail: 'USD ∈ {USD, EUR}', passed: true },
        { label: 'Amount ≤ max_amount', detail: '$4,280 ≤ $10,000', passed: true },
        { label: 'Amount ≤ escalation_threshold', detail: '$4,280 ≤ $5,000', passed: true },
        { label: 'Due date present', detail: '2026-11-15', passed: true },
      ],
      note: 'Result: approved · policy_ok. The recorded decision keeps this rules snapshot.',
    },
  },
  {
    id: 'review',
    number: '04',
    label: 'Review',
    teaser: 'What the engine cannot approve alone.',
    planned: true,
    detail: {
      heading: 'Escalated invoices',
      badge: { text: 'planned', tone: 'escalated' },
      intro: 'Invoices that fail an escalation rule (amount above threshold, missing required data) are held for human decision. The review workflow is planned — today the decision is simply recorded as escalated.',
      fields: [
        { key: 'reason', value: 'amount_exceeds_escalation_threshold' },
        { key: 'context', value: 'policy version + rules snapshot attached' },
        { key: 'human action', value: 'not implemented yet' },
      ],
      note: 'The engine never silently approves. Escalated means: a person should look.',
    },
  },
];

@Component({
  selector: 'pb-invoice-cycle',
  template: `
    <section class="cycle" aria-label="Invoice cycle — interactive walkthrough">
      <ol class="cycle__stages" role="tablist" aria-label="Invoice cycle stages">
        @for (stage of stages(); track stage.id; let i = $index) {
          <li class="cycle__tick" role="presentation">
            <button
              type="button"
              class="cycle__stage"
              [class.is-active]="active() === i"
              role="tab"
              [attr.aria-selected]="active() === i"
              [attr.aria-controls]="'cycle-panel'"
              (click)="select(i)"
              (keydown.enter)="select(i)"
            >
              <span class="cycle__no">{{ stage.number }}</span>
              <span class="cycle__label">{{ stage.label }}</span>
              @if (stage.planned) {
                <span class="cycle__planned">planned</span>
              }
            </button>
            @if (i < stages().length - 1) {
              <span class="cycle__rail" aria-hidden="true"></span>
            }
          </li>
        }
      </ol>

      <div class="cycle__panel" id="cycle-panel" role="tabpanel" [attr.aria-live]="'polite'">
        @if (activeStage(); as stage) {
          <header class="cycle__head">
            <div>
              <h3 class="cycle__title">{{ stage.detail.heading }}</h3>
              <p class="cycle__intro">{{ stage.detail.intro }}</p>
            </div>
            @if (stage.detail.badge; as badge) {
              <span class="cycle__badge" [class]="'cycle__badge--' + badge.tone">
                {{ badge.text }}
              </span>
            }
          </header>

          @if (stage.detail.fields; as fields) {
            <dl class="cycle__fields">
              @for (field of fields; track field.key) {
                <div>
                  <dt>{{ field.key }}</dt>
                  <dd class="pb-mono">{{ field.value }}</dd>
                </div>
              }
            </dl>
          }

          @if (stage.detail.rules; as rules) {
            <ul class="cycle__rules">
              @for (rule of rules; track rule.label) {
                <li [class.is-pass]="rule.passed">
                  <span class="cycle__mark" aria-hidden="true">{{ rule.passed ? '✓' : '✕' }}</span>
                  <span class="cycle__rule-label">{{ rule.label }}</span>
                  <span class="pb-mono cycle__rule-detail">{{ rule.detail }}</span>
                </li>
              }
            </ul>
          }

          <p class="cycle__note">{{ stage.detail.note }}</p>
        }
      </div>
    </section>
  `,
  styles: `
    .cycle {
      display: grid;
      grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
      gap: var(--pb-space-6);
      align-items: start;
    }

    .cycle__stages {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 0;
    }

    .cycle__tick {
      position: relative;
      display: grid;
    }

    .cycle__stage {
      display: grid;
      grid-template-columns: 2.6rem 1fr auto;
      align-items: center;
      gap: var(--pb-space-3);
      width: 100%;
      text-align: left;
      padding: var(--pb-space-3) var(--pb-space-3);
      border: 1px solid transparent;
      border-radius: var(--pb-radius-m);
      background: transparent;
      color: var(--pb-ink-soft);
      font-family: var(--pb-font-body);
      transition: background var(--pb-dur) var(--pb-ease),
        border-color var(--pb-dur) var(--pb-ease);
    }

    .cycle__stage:hover {
      background: var(--pb-surface);
    }

    .cycle__stage.is-active {
      background: var(--pb-surface);
      border-color: var(--pb-line-strong);
    }

    .cycle__no {
      font-family: var(--pb-font-mono);
      font-size: var(--pb-text-sm);
      color: var(--pb-brand-strong);
      font-weight: 600;
    }

    .cycle__label {
      font-family: var(--pb-font-display);
      font-weight: 700;
      font-size: 1rem;
    }

    .cycle__stage.is-active .cycle__label {
      color: var(--pb-ink);
    }

    .cycle__planned {
      font-family: var(--pb-font-mono);
      font-size: 0.625rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--pb-highlight);
    }

    .cycle__rail {
      position: relative;
      height: var(--pb-space-4);
      margin-left: calc(2.6rem + var(--pb-space-3));
      border-left: 1px dashed var(--pb-line-strong);
    }

    .cycle__panel {
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-l);
      background: var(--pb-surface);
      padding: var(--pb-space-5);
      min-width: 0;
    }

    .cycle__head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: var(--pb-space-3);
      padding-bottom: var(--pb-space-3);
      border-bottom: 1px solid var(--pb-line);
    }

    .cycle__title {
      font-size: 1.25rem;
      letter-spacing: -0.02em;
    }

    .cycle__intro {
      margin-top: var(--pb-space-1);
      color: var(--pb-ink-soft);
      font-size: var(--pb-text-sm);
      max-width: 32rem;
    }

    .cycle__badge {
      padding: 0.25rem 0.625rem;
      border-radius: var(--pb-radius-pill);
      font-size: 0.6875rem;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .cycle__badge--approved { color: var(--pb-approved); background: var(--pb-approved-bg); }
    .cycle__badge--escalated { color: var(--pb-escalated); background: var(--pb-escalated-bg); }
    .cycle__badge--blocked { color: var(--pb-blocked); background: var(--pb-blocked-bg); }
    .cycle__badge--planned { color: var(--pb-highlight); background: var(--pb-highlight-soft); }

    .cycle__fields {
      margin: var(--pb-space-3) 0 0;
      display: grid;
      gap: 0;
    }

    .cycle__fields div {
      display: grid;
      grid-template-columns: 8rem 1fr;
      gap: var(--pb-space-3);
      padding: var(--pb-space-2) 0;
      border-bottom: 1px solid var(--pb-line);
      font-size: var(--pb-text-sm);
    }

    .cycle__fields dt {
      color: var(--pb-muted);
    }

    .cycle__fields dd {
      margin: 0;
    }

    .cycle__rules {
      list-style: none;
      margin: var(--pb-space-3) 0 0;
      padding: 0;
      display: grid;
      gap: var(--pb-space-2);
    }

    .cycle__rules li {
      display: grid;
      grid-template-columns: 1.6rem 1fr auto;
      align-items: center;
      gap: var(--pb-space-2);
      padding: var(--pb-space-2) var(--pb-space-3);
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-m);
      font-size: var(--pb-text-sm);
    }

    .cycle__mark {
      width: 20px;
      height: 20px;
      border-radius: var(--pb-radius-pill);
      display: grid;
      place-items: center;
      color: var(--pb-approved);
      background: var(--pb-approved-bg);
      font-weight: 800;
      font-size: 0.75rem;
    }

    .cycle__rule-label {
      font-weight: 600;
    }

    .cycle__rule-detail {
      color: var(--pb-muted);
      font-size: 0.6875rem;
    }

    .cycle__note {
      margin-top: var(--pb-space-3);
      color: var(--pb-muted);
      font-size: var(--pb-text-sm);
    }

    @media (max-width: 900px) {
      .cycle {
        grid-template-columns: 1fr;
        gap: var(--pb-space-5);
      }
    }
  `,
})
export class InvoiceCycle {
  protected readonly stages = signal(STAGES);
  protected readonly active = signal(0);

  protected activeStage(): CycleStage {
    return this.stages()[this.active()];
  }

  protected select(index: number): void {
    this.active.set(index);
  }
}