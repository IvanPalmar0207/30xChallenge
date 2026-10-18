import { animate, style, transition, trigger } from '@angular/animations';
import { Component, signal } from '@angular/core';

import { Icon } from '../../shared/icon';
import { Sound } from '../../shared/sound';
import { DemoInvoice } from './types';

/**
 * Hero stage: one example invoice runs through the evaluation spine.
 * Local demo only — labelled in the UI, never processed by the backend.
 */

const STAGES = ['Receive', 'Evaluate', 'Decide'] as const;

const EXAMPLE: DemoInvoice = {
  id: 'demo-1',
  vendor: 'Northwind Works',
  number: 'INV-2201',
  amount: 4280,
  currency: 'USD',
  dueDate: '2026-11-15',
  description: 'Consulting services',
};

@Component({
  selector: 'pb-hero-demo',
  imports: [Icon],
  animations: [
    trigger('outcome', [
      transition(':enter', [
        style({ opacity: 0, transform: 'translateY(6px)' }),
        animate('240ms cubic-bezier(0.2,0.7,0.2,1)', style({ opacity: 1, transform: 'none' })),
      ]),
    ]),
  ],
  template: `
    <section class="stage" aria-label="Invoice flow demo — example data">
      <header class="stage__bar">
        <span class="stage__tag" aria-hidden="true">Demo · example data</span>
        <span class="stage__seq">INV-2201 · USD</span>
      </header>

      <div class="stage__flow">
        <svg class="stage__spine" viewBox="0 0 420 90" aria-hidden="true">
          <line class="stage__spine-line" x1="30" y1="45" x2="400" y2="45" stroke-width="1.5" stroke-dasharray="3 6" />
          <circle class="stage__runner" cx="30" cy="45" r="5" [attr.transform]="'translate(' + runnerX() + ' 0)'" />
          @for (stage of stageList(); track stage.index) {
            <g class="stage__node" [class.is-done]="activeStage() > stage.index" [class.is-live]="activeStage() === stage.index">
              <circle [attr.cx]="stage.x" cy="45" r="6" />
              <text [attr.x]="stage.x" y="78" text-anchor="middle">{{ stage.label }}</text>
            </g>
          }
        </svg>

        <div class="stage__invoice">
          <svg viewBox="0 0 96 64" aria-hidden="true">
            <rect class="stage__doc-rect" x="4" y="2" width="88" height="60" rx="4" stroke-width="1.5" />
            <path class="stage__doc-lines" d="M12 14h40M12 21h28M12 28h52M12 35h52M12 42h34" stroke-width="1.5" stroke-linecap="round" />
            <circle class="stage__doc-check-ring" cx="72" cy="40" r="9" stroke-width="1.5" />
            <path class="stage__doc-check" d="M68.4 40l2.6 2.6 4.8-5.4" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span class="stage__amount pb-mono">$4,280.00</span>
        </div>

        <div class="stage__outcome" [attr.aria-live]="'polite'">
          @if (activeStage() < 1) {
            <p class="stage__outcome-idle">Ready — no policy consulted yet.</p>
          } @else if (activeStage() === 1) {
            <p class="stage__outcome-run">
              <span class="orb" aria-hidden="true"><i></i><i></i><i></i></span>
              Checking active policy…
            </p>
          } @else {
            <p class="stage__outcome-done" @outcome>
              <span class="stage__badge stage__badge--approved">
                <pb-icon name="check" />
                approved
              </span>
              <span class="pb-mono">policy_ok</span>
              — the example invoice satisfies every rule.
            </p>
          }
        </div>
      </div>

      <button
        type="button"
        class="pb-btn pb-btn--primary stage__run"
        (click)="run()"
        [disabled]="running()"
      >
        {{ running() ? 'Evaluating…' : 'Run evaluation (demo)' }}
      </button>
    </section>
  `,
  styles: `
    .stage {
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-l);
      background: var(--pb-surface);
      box-shadow: var(--pb-shadow-card);
      overflow: hidden;
    }

    .stage__bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--pb-space-3);
      padding: var(--pb-space-3) var(--pb-space-4);
      border-bottom: 1px solid var(--pb-line);
    }

    .stage__tag {
      font-family: var(--pb-font-mono);
      font-size: 0.625rem;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--pb-highlight);
    }

    .stage__seq {
      font-family: var(--pb-font-mono);
      font-size: 0.6875rem;
      color: var(--pb-muted);
    }

    .stage__flow {
      padding: var(--pb-space-4) var(--pb-space-5) var(--pb-space-3);
      display: grid;
      justify-items: center;
      gap: var(--pb-space-4);
    }

    .stage__spine {
      width: 100%;
      max-width: 420px;
      height: auto;
    }

    .stage__spine-line {
      stroke: var(--pb-line-strong);
    }

    .stage__doc-rect {
      fill: var(--pb-surface);
      stroke: var(--pb-line-strong);
    }

    .stage__doc-lines {
      stroke: var(--pb-muted);
    }

    .stage__doc-check-ring {
      fill: none;
      stroke: var(--pb-brand-strong);
    }

    .stage__doc-check {
      stroke: var(--pb-brand-strong);
    }

    .stage__node circle {
      fill: var(--pb-surface);
      stroke: var(--pb-line-strong);
      stroke-width: 2;
      transition: fill var(--pb-dur) var(--pb-ease),
        stroke var(--pb-dur) var(--pb-ease);
    }

    .stage__node.is-done circle {
      fill: var(--pb-brand);
      stroke: var(--pb-brand);
    }

    .stage__node.is-live circle {
      stroke: var(--pb-accent);
      stroke-width: 3;
      fill: var(--pb-surface);
    }

    .stage__node text {
      font-family: var(--pb-font-mono);
      font-size: 9px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      fill: var(--pb-muted);
    }

    .stage__node.is-done text {
      fill: var(--pb-ink);
    }

    .stage__runner {
      fill: var(--pb-accent-strong);
      stroke: var(--pb-surface);
      stroke-width: 2;
      transition: transform var(--pb-dur-slow) var(--pb-ease);
      will-change: transform;
    }

    .stage__invoice {
      display: grid;
      justify-items: center;
      gap: var(--pb-space-1);
    }

    .stage__invoice svg {
      width: 96px;
      height: auto;
      stroke-width: 0;
    }

    .stage__amount {
      font-size: 1.0625rem;
      font-weight: 600;
      color: var(--pb-ink);
    }

    .stage__outcome {
      min-height: 2.5rem;
      text-align: center;
      font-size: var(--pb-text-sm);
      color: var(--pb-ink-soft);
    }

    .stage__outcome-run {
      color: var(--pb-accent);
      display: inline-flex;
      align-items: center;
      gap: var(--pb-space-2);
    }

    .orb {
      display: inline-flex;
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

    .stage__outcome-done {
      display: inline-flex;
      align-items: center;
      gap: var(--pb-space-2);
      flex-wrap: wrap;
      justify-content: center;
    }

    .stage__badge {
      display: inline-flex;
      align-items: center;
      gap: 0.375rem;
      padding: 0.25rem 0.625rem;
      border-radius: var(--pb-radius-pill);
      font-weight: 800;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      font-size: 0.75rem;
    }

    .stage__badge--approved {
      color: var(--pb-approved);
      background: var(--pb-approved-bg);
    }

    .stage__badge pb-icon {
      font-size: 0.8125rem;
    }

    .stage__run {
      width: 100%;
      border-radius: 0;
      border: 0;
      border-top: 1px solid var(--pb-line);
      padding: 0.875rem;
    }
  `,
})
export class HeroDemo {
  protected readonly STAGES = STAGES;
  protected readonly activeStage = signal(-1);
  protected readonly running = signal(false);
  private timers: number[] = [];

  constructor(private readonly sound: Sound) {}

  protected stageList() {
    return STAGES.map((label, index) => ({ label, index, x: 30 + index * 180 }));
  }

  protected runnerX(): number {
    if (this.activeStage() < 0) return 0;
    return Math.min(this.activeStage(), 2) * 180;
  }

  run(): void {
    if (this.running()) return;
    this.sound.setEnabled(false); // keep the hero silent; demo sounds live in the lab
    this.running.set(true);
    this.activeStage.set(0);
    const delays = [520, 1100, 400];
    let acc = 0;
    delays.forEach((ms, i) => {
      acc += ms;
      this.timers.push(
        window.setTimeout(() => {
          this.activeStage.set(i + 1);
          if (i === 2) {
            this.running.set(false);
          } else {
            this.sound.tick();
          }
        }, acc),
      );
    });
  }

  ngOnDestroy(): void {
    this.timers.forEach((t) => window.clearTimeout(t));
  }
}