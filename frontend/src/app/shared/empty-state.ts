import { Component, input } from '@angular/core';

/**
 * Honest empty state with an optional list of concrete next steps.
 * Never shows fake data; when steps exist they are real, navigable advice.
 */
@Component({
  selector: 'pb-empty-state',
  template: `
    <div class="empty">
      <svg class="empty__mark" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
        <rect x="6" y="10" width="36" height="28" rx="3" fill="none" stroke="currentColor" stroke-width="1.5" />
        <path d="M6 17h36" stroke="currentColor" stroke-width="1.5" />
        <path d="M12 24h9M12 29h9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      </svg>

      <div class="empty__text">
        <h3 class="empty__title">{{ title() }}</h3>
        <p class="empty__body">{{ body() }}</p>

        @if (steps().length) {
          <ol class="empty__steps">
            @for (step of steps(); track $index) {
              <li>{{ step }}</li>
            }
          </ol>
        }
      </div>

      <span class="empty__flag">not connected yet</span>
    </div>
  `,
  styles: `
    .empty {
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: var(--pb-space-4);
      align-items: start;
      padding: var(--pb-space-5) var(--pb-space-5);
      border: 1px solid var(--pb-line);
      border-left: 3px solid var(--pb-line-strong);
      border-radius: var(--pb-radius-m);
      background: var(--pb-surface-2);
    }

    .empty__mark {
      width: 34px;
      height: 34px;
      color: var(--pb-muted);
    }

    .empty__title {
      font-size: 1rem;
    }

    .empty__body {
      margin-top: var(--pb-space-1);
      color: var(--pb-ink-soft);
      font-size: var(--pb-text-sm);
      max-width: 36rem;
    }

    .empty__steps {
      margin: var(--pb-space-3) 0 0;
      padding-left: var(--pb-space-5);
      display: grid;
      gap: var(--pb-space-1);
      color: var(--pb-ink-soft);
      font-size: var(--pb-text-sm);
    }

    .empty__flag {
      font-family: var(--pb-font-mono);
      font-size: 0.625rem;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--pb-muted);
      white-space: nowrap;
    }

    @media (max-width: 640px) {
      .empty {
        grid-template-columns: 1fr;
      }
    }
  `,
})
export class EmptyState {
  readonly title = input('');
  readonly body = input('');
  readonly steps = input<string[]>([]);
}