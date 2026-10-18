import { CommonModule } from '@angular/common';
import { Component, OnDestroy, computed, signal, type Signal, inject } from '@angular/core';
import { toObservable } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Subscription, forkJoin, take } from 'rxjs';

import { Folio } from '../../shared/folio';
import { Icon } from '../../shared/icon';
import { AuthService } from '../../core/auth/auth.service';
import { UserProfile } from '../../core/auth/models';
import { InvoicesService } from '../invoices/invoices.service';
import { InvoiceStatus, InvoiceSummary } from '../invoices/invoices.models';
import { PoliciesService } from '../policies/policies.service';
import { PolicyVersion } from '../policies/policies.models';

type LoadState = 'loading' | 'ready' | 'forbidden' | 'error' | 'noorganization';

const STATUS_LABEL: Record<InvoiceStatus, string> = {
  received: 'received',
  pending_approval: 'pending approval',
  approved: 'approved',
  blocked: 'blocked',
  escalated: 'escalated',
  rejected: 'rejected',
};

const STATUS_ORDER: InvoiceStatus[] = [
  'received',
  'pending_approval',
  'approved',
  'blocked',
  'escalated',
  'rejected',
];

/**
 * Dashboard — real-data summary of the active organization.
 *
 * Uses only two org-scoped reads (invoices + policies), issued once in
 * parallel; organization identity comes from the session membership (the
 * same server that scopes every request), so no redundant /organizations/
 * call is made. Every indicator shown is a plain count or a field the
 * backend already returns: no financial totals are computed (invoices may
 * mix currencies and the API offers no aggregate), and no status or rule is
 * invented. Navigation points to Vendors and Invoices.
 */
@Component({
  selector: 'pb-dashboard',
  imports: [CommonModule, Folio, Icon, RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnDestroy {
  protected readonly user!: Signal<UserProfile | null>;
  protected readonly state = signal<LoadState>('loading');
  protected readonly invoices = signal<InvoiceSummary[]>([]);
  protected readonly policies = signal<PolicyVersion[]>([]);
  protected readonly orgName = signal('—');

  private sub?: Subscription;
  private readonly user$ = toObservable(this.user);

  constructor(
    private readonly invoicesService: InvoicesService,
    private readonly policiesService: PoliciesService,
    private readonly auth: AuthService,
  ) {
    this.user = this.auth.user;
    if (this.user()) {
      this.load();
    } else {
      this.sub = this.user$.pipe(take(1)).subscribe(() => this.load());
    }
  }

  protected load(): void {
    const membership = this.auth.currentMembership();
    const orgId = membership?.organization_id;
    if (!orgId) {
      this.state.set('noorganization');
      return;
    }
    this.orgName.set(membership?.organization_name ?? '—');
    this.sub?.unsubscribe();
    this.state.set('loading');
    this.sub = forkJoin({
      invoices: this.invoicesService.list(orgId),
      policies: this.policiesService.list(orgId),
    }).subscribe({
      next: ({ invoices, policies }) => {
        this.invoices.set(invoices);
        this.policies.set(policies);
        this.state.set('ready');
      },
      error: (error: { status?: number }) => {
        this.state.set(error.status === 403 ? 'forbidden' : 'error');
      },
    });
  }

  // ── indicators (plain counts over the server responses) ────────────────

  protected readonly totalInvoices = computed(() => this.invoices().length);

  protected readonly statusCounts = computed(() => {
    const counts: Record<InvoiceStatus, number> = {
      received: 0,
      pending_approval: 0,
      approved: 0,
      blocked: 0,
      escalated: 0,
      rejected: 0,
    };
    for (const invoice of this.invoices()) {
      counts[invoice.status] = (counts[invoice.status] ?? 0) + 1;
    }
    return counts;
  });

  protected readonly statusOrder = STATUS_ORDER;

  /** Blocked + escalated + pending approval: the attention tray. */
  protected readonly attentionCount = computed(() => {
    const counts = this.statusCounts();
    return counts.blocked + counts.escalated + counts.pending_approval;
  });

  protected readonly activePolicy = computed(
    () => this.policies().find((p) => p.is_active) ?? null,
  );

  protected readonly policyVersionCount = computed(() => this.policies().length);

  /** Backend orders invoices by -created_at, so the slice is newest-first. */
  protected readonly recentInvoices = computed(() => this.invoices().slice(0, 5));

  protected statusLabel(status: InvoiceStatus): string {
    return STATUS_LABEL[status] ?? status;
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}
