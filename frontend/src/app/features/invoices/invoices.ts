import { CommonModule } from '@angular/common';
import { Component, OnDestroy, signal, type Signal, inject } from '@angular/core';
import { toObservable } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { Subscription, take } from 'rxjs';

import { Folio } from '../../shared/folio';
import { AuthService } from '../../core/auth/auth.service';
import { CapabilitiesService } from '../../core/auth/capabilities.service';
import { UserProfile } from '../../core/auth/models';
import { InvoicesService } from './invoices.service';
import { InvoiceStatus, InvoiceSummary } from './invoices.models';

type LoadState =
  | 'loading'
  | 'ready'
  | 'forbidden'
  | 'error'
  | 'noorganization';

const STATUS_LABEL: Record<InvoiceStatus, string> = {
  received: 'received',
  pending_approval: 'pending approval',
  approved: 'approved',
  blocked: 'blocked',
  escalated: 'escalated',
  rejected: 'rejected',
};

/**
 * Invoices — read-only list of the active organization's invoices.
 * The organization comes from /auth/me/ (first membership), the same source
 * the rest of the shell uses. Loading, empty, forbidden, server-error and
 * no-organization states are explicit; no financial actions are shown here.
 */
@Component({
  selector: 'pb-invoices',
  imports: [CommonModule, Folio],
  templateUrl: './invoices.html',
  styleUrl: './invoices.scss',
})
export class InvoicesPage implements OnDestroy {
  protected readonly user!: Signal<UserProfile | null>;
  protected readonly state = signal<LoadState>('loading');
  protected readonly invoices = signal<InvoiceSummary[]>([]);

  private sub?: Subscription;
  private readonly user$ = toObservable(this.user);

  protected readonly cap = inject(CapabilitiesService);

  constructor(
    private readonly service: InvoicesService,
    private readonly auth: AuthService,
    private readonly router: Router,
  ) {
    this.user = this.auth.user;
    // load() handles the no-membership case itself. Only when the user has
    // not been populated yet (restoration may finish slightly after the route
    // resolves) do we wait for it — avoids the stale "no organization" state.
    if (this.user()) {
      this.load();
    } else {
      this.sub = this.user$.pipe(take(1)).subscribe(() => this.load());
    }
  }

  goInvoiceCreate(): void {
    void this.router.navigate(['/app/invoices/upload']);
  }

  protected load(): void {
    const orgId = this.auth.currentMembership()?.organization_id;
    if (!orgId) {
      this.state.set('noorganization');
      return;
    }
    this.sub?.unsubscribe();
    this.state.set('loading');
    this.sub = this.service.list(orgId).subscribe({
      next: (rows) => {
        this.invoices.set(rows);
        this.state.set('ready');
      },
      error: (error: { status?: number }) => {
        this.state.set(error.status === 403 ? 'forbidden' : 'error');
      },
    });
  }

  protected statusLabel(status: InvoiceStatus): string {
    return STATUS_LABEL[status] ?? status;
  }

  protected orgName(): string {
    return this.auth.currentMembership()?.organization_name ?? '—';
  }

  protected open(id: string): void {
    void this.router.navigate(['/app/invoices', id]);
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}