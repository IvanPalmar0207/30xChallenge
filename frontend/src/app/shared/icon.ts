import { Component, input } from '@angular/core';

/**
 * Minimal SVG icon set in the lucide style (stroke 2, round caps) drawn
 * in-house — no icon dependency; every glyph is a crisp 24×24 path.
 */

const PATHS: Record<string, string> = {
  check: 'M20 6 9 17l-5-5',
  x: 'M18 6 6 18M6 6l12 12',
  alert: 'M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  search: 'm21 21-4.3-4.3M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z',
  arrowRight: 'M5 12h14m-6-6 6 6-6 6',
  close: 'M18 6 6 18M6 6l12 12',
  loader: 'M12 3a9 9 0 1 0 9 9',
  chevronDown: 'm6 9 6 6 6-6',
};

@Component({
  selector: 'pb-icon',
  template: `
    <svg
      class="icon"
      [class.icon--spin]="spin()"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      [attr.aria-hidden]="true"
    >
      <path [attr.d]="PATHS[name()] ?? ''" />
    </svg>
  `,
  styles: `
    .icon {
      width: 1em;
      height: 1em;
      flex: none;
    }

    .icon--spin {
      animation: pb-spin 0.9s linear infinite;
    }

    @keyframes pb-spin {
      to {
        transform: rotate(360deg);
      }
    }
  `,
})
export class Icon {
  readonly name = input<'check' | 'x' | 'alert' | 'search' | 'arrowRight' | 'close' | 'loader' | 'chevronDown'>('check');
  readonly spin = input(false);

  protected readonly PATHS = PATHS;
}