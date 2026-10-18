import { Component, input } from '@angular/core';

/**
 * PayBlood wordmark — original bank-grade symbol.
 *
 * Concept: the "P" of PayBlood drawn as a ledger stem and open bowl; a
 * verification check crosses the bowl and carries the decision point (the
 * orange dot) — every invoice passes one deterministic evaluation. One mark,
 * two meanings: document + verification.
 *
 * Variants: `inverted` for dark surfaces. Proportions are fixed; the mark
 * stays legible down to favicon size.
 */
@Component({
  selector: 'pb-logo',
  template: `
    <span class="logo" [class.logo--inverted]="inverted()">
      <svg
        class="logo__mark"
        viewBox="0 0 28 28"
        role="img"
        aria-label="PayBlood"
        focusable="false"
      >
        <path
          class="logo__stem"
          d="M8.6 5.5v17"
          fill="none"
          stroke-width="2.6"
          stroke-linecap="round"
        />
        <path
          class="logo__bowl"
          d="M8.6 5.5h6.2a4.7 4.7 0 0 1 0 9.4H8.6"
          fill="none"
          stroke-width="2.6"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <path
          class="logo__check"
          d="M16.4 22.6l3.1 3.2 6-8.6"
          fill="none"
          stroke-width="2.6"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <circle class="logo__point" cx="19.5" cy="19.6" r="1.7" />
      </svg>
      <span class="logo__word">Pay<span class="logo__word-blood">Blood</span></span>
    </span>
  `,
  styles: `
    .logo {
      display: inline-flex;
      align-items: center;
      gap: 0.6rem;
      color: var(--pb-ink);
    }

    .logo__mark {
      width: 30px;
      height: 30px;
      color: var(--pb-brand-strong);
    }

    .logo--inverted {
      color: #fff;
    }

    .logo--inverted .logo__mark {
      color: #fff;
    }

    .logo--inverted .logo__point {
      fill: var(--pb-lime-invert, #b8e34c);
    }

    .logo__stem,
    .logo__bowl,
    .logo__check {
      stroke: currentColor;
    }

    .logo--inverted .logo__stem,
    .logo--inverted .logo__bowl,
    .logo--inverted .logo__check {
      stroke: #fff;
    }

    .logo__point {
      fill: var(--pb-accent-strong);
    }

    .logo__word {
      font-family: var(--pb-font-display);
      font-weight: 700;
      font-size: 1.1875rem;
      letter-spacing: -0.03em;
      line-height: 1;
    }

    .logo__word-blood {
      color: var(--pb-accent-strong);
    }

    .logo--inverted .logo__word {
      color: #fff;
    }

    .logo--inverted .logo__word-blood {
      color: var(--pb-lime-invert, #b8e34c);
    }
  `,
})
export class Logo {
  readonly inverted = input(false);
}