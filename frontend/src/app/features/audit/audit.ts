import { Component } from '@angular/core';

import { Folio } from '../../shared/folio';
import { EmptyState } from '../../shared/empty-state';

/**
 * Audit — activity trail. The backend records append-only events with actor,
 * organization, action, target and safe metadata; no public audit read
 * endpoint exists yet, so this section explains the model instead of faking
 * a feed.
 */
@Component({
  selector: 'pb-audit',
  imports: [Folio, EmptyState],
  template: `
    <pb-folio [seq]="6" label="Administration · Audit" />

    <header class="pb-page-head">
      <h1 class="pb-page-title">Audit</h1>
      <p class="pb-page-lede">
        Every mutation commits an append-only audit event in the same
        transaction: actor, organization, action, target and safe metadata —
        never tokens, hashes or full request bodies.
      </p>
    </header>

    <div class="actions" aria-label="Audit event actions">
      <span class="event event--ledger">account_created</span>
      <span class="event event--ledger">membership_role_changed</span>
      <span class="event event--ledger">vendor_activated</span>
      <span class="event event--ledger">invoice_created</span>
      <span class="event event--ledger">invoice_evaluated</span>
      <span class="event event--ledger">policy_created</span>
      <span class="event event--ledger">invitation_issued</span>
      <span class="event event--ledger">password_set</span>
    </div>

    <pb-empty-state
      title="No audit feed yet"
      body="The backend has no audit read/export endpoint at this stage, so no
      feed is shown here. The Django admin remains the only authorized read
      path for the trail."
      [steps]="[
        'Use the Django admin for the current trail',
        'An audit read endpoint is a planned contract addition',
      ]"
    />
  `,
  styles: `
    .pb-page-head {
      border-bottom: 1px solid var(--pb-line);
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: var(--pb-space-2);
      margin-bottom: var(--pb-space-5);
    }

    .event {
      padding: 0.375rem 0.75rem;
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-pill);
      background: var(--pb-surface);
      font-family: var(--pb-font-mono);
      font-size: 0.75rem;
      color: var(--pb-ink-soft);
    }

    .event--ledger::before {
      content: '◦ ';
      color: var(--pb-brand-strong);
    }
  `,
})
export class AuditPage {}