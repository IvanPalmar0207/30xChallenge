import { CommonModule } from '@angular/common';
import { Component, OnDestroy, signal, type Signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import { Folio } from '../../shared/folio';
import { Icon } from '../../shared/icon';
import { AuthService } from '../../core/auth/auth.service';
import { MembershipSummary } from '../../core/auth/models';
import { OrganizationsService } from './organizations.service';
import { OrganizationSummary } from './organizations.models';

type LoadState = 'loading' | 'ready' | 'forbidden' | 'error';

/**
 * Organizations — first real API integration. Read-only list scoped by the
 * backend to the user's active memberships; the "active" organization is the
 * one /auth/me/ resolved as the first membership (both come from the same
 * server). Loading, empty, forbidden and server-error states are explicit.
 */
@Component({
  selector: 'pb-organizations',
  imports: [CommonModule, Folio, Icon, RouterLink],
  templateUrl: './organizations.html',
  styleUrl: './organizations.scss',
})
export class OrganizationsPage implements OnDestroy {
  protected user!: Signal<import('../../core/auth/models').UserProfile | null>;
  protected readonly state = signal<LoadState>('loading');
  protected readonly organizations = signal<OrganizationSummary[]>([]);
  protected readonly activeOrgId = signal<string | null>(null);

  private sub?: Subscription;

  constructor(
    private readonly orgs: OrganizationsService,
    private readonly auth: AuthService,
  ) {
    this.user = this.auth.user;
    this.load();
  }

  protected load(): void {
    this.sub?.unsubscribe();
    this.state.set('loading');
    this.sub = this.orgs.list().subscribe({
      next: (orgs) => {
        this.organizations.set(orgs);
        this.activeOrgId.set(this.auth.currentMembership()?.organization_id ?? null);
        this.state.set('ready');
      },
      error: (error: { status?: number }) => {
        this.state.set(error.status === 403 ? 'forbidden' : 'error');
      },
    });
  }

  protected roleOf(orgId: string): string {
    const membership: MembershipSummary | undefined = this.user()?.memberships?.find(
      (m) => m.organization_id === orgId,
    );
    return membership ? membership.role : '—';
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}