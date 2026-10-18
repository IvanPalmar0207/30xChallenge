import { CommonModule } from '@angular/common';
import { Component, input } from '@angular/core';

/**
 * "Folio" label — the numbered bookkeeping tag (SEQ. 0007 · INVOICES)
 * that gives PayBlood its ledger identity. Decorative, aria-hidden.
 */
@Component({
  selector: 'pb-folio',
  imports: [CommonModule],
  template: `
    <p class="pb-folio" aria-hidden="true">
      <span>SEQ. {{ seq() | number: '3.0-0' }}</span>
      <span aria-hidden="true">·</span>
      <span>{{ label() }}</span>
    </p>
  `,
})
export class Folio {
  readonly seq = input.required<number>();
  readonly label = input('');
}