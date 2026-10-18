import { Component, signal } from '@angular/core';

/**
 * Interactive "anatomy of an invoice" — an original SVG diagram (Skills
 * Anatomy adapted: an exploded mechanical view instead of a generic
 * ornament). Four labeled stages of the invoice cycle; each node is focusable
 * and keyboard-selectable, and the selection updates a live region so the
 * description never relies on color or visuals alone.
 *
 * Honesty rule: stages not implemented yet are explicitly marked "planned".
 */

interface AnatomyStage {
  id: string;
  number: string;
  label: string;
  desc: string;
  planned: boolean;
}

const STAGES: AnatomyStage[] = [
  {
    id: 'receive',
    number: '01',
    label: 'Receive',
    desc: 'The invoice enters the organization and is registered with server-assigned status received.',
    planned: false,
  },
  {
    id: 'extract',
    number: '02',
    label: 'Extract',
    desc: 'Fields are structured for evaluation — vendor, invoice number, dates, amount, currency. Automated extraction is a planned phase, not yet implemented.',
    planned: true,
  },
  {
    id: 'evaluate',
    number: '03',
    label: 'Evaluate',
    desc: 'The deterministic engine applies the active policy and records one decision with its rules snapshot. Blocked, escalated, or approved.',
    planned: false,
  },
  {
    id: 'review',
    number: '04',
    label: 'Review',
    desc: 'Anything the engine cannot safely approve stays out of any silent pass: escalated invoices are meant for human decision (workflow planned).',
    planned: true,
  },
];

const STEP_Y = 108; // vertical stride of the nodes

@Component({
  selector: 'pb-invoice-anatomy',
  template: `
    <figure class="anatomy">
      <svg
        class="anatomy__svg"
        viewBox="0 0 320 480"
        role="img"
        aria-labelledby="anatomy-title"
      >
        <title id="anatomy-title">Anatomy of an invoice cycle — four stages</title>
        <desc>
          Receive, Extract, Evaluate and Review. Each stage is selectable.
        </desc>

        <!-- spine with travelling runner (progress point) -->
        <line class="anatomy__spine" x1="60" y1="40" x2="60" y2="470" stroke-width="1.5" stroke-dasharray="4 6" />
        <circle
          class="anatomy__runner"
          cx="60"
          cy="52"
          r="4"
          [attr.transform]="'translate(0 ' + (activeIndex() * stepY + 6) + ')'"
          aria-hidden="true"
        />

        <!-- travelling document -->
        <g
          class="anatomy__doc"
          [attr.transform]="'translate(0 ' + (activeIndex() * stepY + 6) + ')'"
          aria-hidden="true"
        >
          <rect x="38" y="34" width="44" height="36" rx="6" fill="var(--pb-surface)" stroke="var(--pb-brand-strong)" stroke-width="2" />
          <path d="M46 46h28M46 52h28M46 58h18" stroke="var(--pb-muted)" stroke-width="2" stroke-linecap="round" />
        </g>

        @for (stage of stages; track stage.id; let i = $index) {
        <g
          class="anatomy__node"
          [class.is-active]="i === activeIndex()"
          [attr.tabindex]="i === activeIndex() ? 0 : -1"
          role="button"
          [attr.aria-pressed]="i === activeIndex()"
          [attr.aria-current]="i === activeIndex() ? 'true' : null"
          [attr.aria-label]="'Stage ' + stage.number + ': ' + stage.label"
          (click)="select(i)"
          (keydown.enter)="select(i)"
          (keydown.space)="select(i); $event.preventDefault()"
          (focus)="select(i)"
        >
          <rect x="84" [attr.y]="i * stepY + 18" width="212" height="72" rx="14" class="anatomy__plate" />
          <text x="106" [attr.y]="i * stepY + 58" class="anatomy__num" text-anchor="middle">{{ stage.number }}</text>
          <text x="150" [attr.y]="i * stepY + 55" class="anatomy__label">{{ stage.label }}</text>
          @if (stage.planned) {
            <text x="150" [attr.y]="i * stepY + 76" class="anatomy__planned">planned</text>
          }
        </g>
        }
      </svg>

      <figcaption class="anatomy__caption">
        <output class="anatomy__desc" aria-live="polite">
          <strong class="anatomy__desc-title">{{ active().number }} · {{ active().label }}</strong>
          <span class="anatomy__desc-body">{{ active().desc }}</span>
          @if (active().planned) {
            <span class="anatomy__desc-flag">planned</span>
          }
        </output>
      </figcaption>
    </figure>
  `,
  styles: `
    .anatomy {
      margin: 0;
      display: grid;
      justify-items: center;
      gap: var(--pb-space-2);
    }

    .anatomy__svg {
      width: min(320px, 100%);
      height: auto;
    }

    .anatomy__plate {
      fill: var(--pb-surface);
      stroke: var(--pb-line-strong);
      stroke-width: 1.5;
      transition: fill var(--pb-dur) var(--pb-ease), stroke var(--pb-dur) var(--pb-ease);
    }

    .anatomy__node:focus-visible .anatomy__plate,
    .anatomy__node.is-active .anatomy__plate {
      fill: var(--pb-brand-soft);
      stroke: var(--pb-brand-strong);
      stroke-width: 2;
    }

    .anatomy__spine {
      stroke: var(--pb-line-strong);
    }

    .anatomy__node:focus-visible {
      outline: none;
    }

    .anatomy__node:focus-visible .anatomy__plate {
      outline: 2px solid var(--pb-focus);
      outline-offset: 2px;
    }

    .anatomy__num {
      font-family: var(--pb-font-mono);
      font-size: 13px;
      font-weight: 700;
      fill: var(--pb-brand-text);
    }

    .anatomy__label {
      font-family: var(--pb-font-display);
      font-size: 17px;
      font-weight: 650;
      fill: var(--pb-ink);
    }

    .anatomy__planned {
      font-family: var(--pb-font-mono);
      font-size: 10px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      fill: var(--pb-bg);
    }

    .anatomy__node:not(.is-active) .anatomy__planned {
      display: none;
    }

    .anatomy__node.is-active .anatomy__planned {
      fill: var(--pb-highlight);
      font-weight: 700;
    }

    .anatomy__doc,
    .anatomy__runner {
      transition: transform var(--pb-dur-slow) var(--pb-ease);
      will-change: transform;
    }

    .anatomy__runner {
      fill: var(--pb-accent-strong);
      stroke: var(--pb-surface);
      stroke-width: 1.5;
    }

    .anatomy__desc {
      display: block;
      min-height: 6.5rem;
      max-width: 320px;
      padding: var(--pb-space-3) var(--pb-space-4);
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-m);
      background: var(--pb-surface);
      font-size: 0.875rem;
      color: var(--pb-ink-soft);
    }

    .anatomy__desc-title {
      display: block;
      color: var(--pb-ink);
      font-family: var(--pb-font-display);
      font-size: 0.9375rem;
    }

    .anatomy__desc-body {
      display: block;
      margin-top: var(--pb-space-1);
    }

    .anatomy__desc-flag {
      display: inline-block;
      margin-top: var(--pb-space-2);
      font-family: var(--pb-font-mono);
      font-size: 0.6875rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--pb-highlight);
    }
  `,
})
export class InvoiceAnatomy {
  protected readonly stages = STAGES;
  protected readonly activeIndex = signal(0);
  protected readonly stepY = STEP_Y;

  protected active(): AnatomyStage {
    return this.stages[this.activeIndex()];
  }

  protected select(index: number): void {
    this.activeIndex.set(index);
  }
}