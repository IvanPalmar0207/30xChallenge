import { CommonModule } from '@angular/common';
import { Component, OnDestroy, computed, signal, type Signal, inject } from '@angular/core';
import { toObservable } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { Subscription, take } from 'rxjs';

import { Folio } from '../../shared/folio';
import { Icon } from '../../shared/icon';
import { AuthService } from '../../core/auth/auth.service';
import { CapabilitiesService } from '../../core/auth/capabilities.service';
import { UserProfile } from '../../core/auth/models';
import { PoliciesService } from './policies.service';
import { PolicyVersion } from './policies.models';

type LoadState = 'loading' | 'ready' | 'forbidden' | 'error' | 'noorganization';

/**
 * Policies — versioned, immutable rule sets served by the backend (Slice 6).
 *
 * Reads are open to any active member; creating a new version is
 * FINANCE_ADMIN-only and the API deactivates the previous version (one
 * active policy per organization). The engine remains solely responsible
 * for financial evaluation — this page only lists rule versions and creates
 * new ones; there is no update or delete (the backend offers none).
 */
@Component({
  selector: 'pb-policies',
  imports: [CommonModule, FormsModule, Folio, Icon],
  templateUrl: './policies.html',
  styleUrl: './policies.scss',
})
export class PoliciesPage implements OnDestroy {
  protected readonly user!: Signal<UserProfile | null>;
  protected readonly state = signal<LoadState>('loading');
  protected readonly policies = signal<PolicyVersion[]>([]);
  protected readonly orgName = signal('—');

  // Create form state (FINANCE_ADMIN only).
  protected readonly showForm = signal(false);
  protected readonly currencies = signal('');
  protected readonly maxAmount = signal('');
  protected readonly escalationThreshold = signal('');
  protected readonly requireDueDate = signal(false);
  protected readonly requireDescription = signal(false);
  protected readonly submitting = signal(false);
  protected readonly formError = signal('');
  protected readonly actionError = signal('');
  protected readonly successNote = signal('');

  private sub?: Subscription;
  private readonly user$ = toObservable(this.user);
  private orgId?: string;

  protected readonly cap = inject(CapabilitiesService);

  /** The active version is the one the engine will evaluate invoices with. */
  protected readonly activePolicy = computed(
    () => this.policies().find((p) => p.is_active) ?? null,
  );

  constructor(
    private readonly service: PoliciesService,
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
    this.orgId = orgId;
    this.orgName.set(membership?.organization_name ?? '—');
    this.sub?.unsubscribe();
    this.state.set('loading');
    this.sub = this.service.list(orgId).subscribe({
      next: (rows) => {
        this.policies.set(rows);
        this.state.set('ready');
      },
      error: (error: { status?: number }) => {
        this.state.set(error.status === 403 ? 'forbidden' : 'error');
      },
    });
  }

  protected isAdmin(): boolean {
    return this.cap.canManagePolicies();
  }

  /** [] means no currency restriction (backend semantics). */
  protected currenciesLabel(policy: PolicyVersion): string {
    return policy.allowed_currencies.length
      ? policy.allowed_currencies.join(', ')
      : 'none (no restriction)';
  }

  protected limitLabel(value: string | null): string {
    return value === null ? 'no cap' : value;
  }

  protected requiresLabel(policy: PolicyVersion): string {
    const flags: string[] = [];
    if (policy.require_due_date) flags.push('due date');
    if (policy.require_description) flags.push('description');
    return flags.length ? flags.join(' & ') : 'none';
  }

  // ── create workflow ─────────────────────────────────────────────────────

  protected openCreate(): void {
    this.showForm.set(true);
    this.currencies.set('');
    this.maxAmount.set('');
    this.escalationThreshold.set('');
    this.requireDueDate.set(false);
    this.requireDescription.set(false);
    this.formError.set('');
    this.successNote.set('');
  }

  protected closeCreate(): void {
    this.showForm.set(false);
    this.formError.set('');
  }

  protected canSubmit(): boolean {
    return !this.submitting();
  }

  /**
   * Submit a new policy version. The payload mirrors the backend serializer
   * (empty strings become null; empty currency list means no restriction).
   * Client-side checks mirror the backend's documented rules, but the API
   * re-validates and remains the authority.
   */
  protected submit(): void {
    if (!this.orgId || !this.canSubmit()) return;
    const currencies = Array.from(
      new Set(
        this.currencies()
          .split(',')
          .map((code) => code.trim().toUpperCase())
          .filter((code) => code.length > 0),
      ),
    );
    const max = this.maxAmount().trim();
    const threshold = this.escalationThreshold().trim();

    if (max !== '' && Number(max) <= 0) {
      this.formError.set('max_amount must be greater than zero.');
      return;
    }
    if (threshold !== '' && Number(threshold) <= 0) {
      this.formError.set('escalation_threshold must be greater than zero.');
      return;
    }
    if (max !== '' && threshold !== '' && Number(threshold) > Number(max)) {
      this.formError.set(
        'escalation_threshold must not exceed max_amount: amounts above max_amount are blocked first.',
      );
      return;
    }

    this.submitting.set(true);
    this.formError.set('');
    this.service
      .create(this.orgId, {
        allowed_currencies: currencies,
        max_amount: max === '' ? null : max,
        escalation_threshold: threshold === '' ? null : threshold,
        require_due_date: this.requireDueDate(),
        require_description: this.requireDescription(),
      })
      .subscribe({
        next: (created) => {
          this.submitting.set(false);
          this.closeCreate();
          this.successNote.set(
            `Policy v${created.version} created and now active. The previous version, if any, was deactivated by the API.`,
          );
          this.load();
        },
        error: (error) => {
          this.submitting.set(false);
          this.formError.set(
            this.apiMessage(error, 'The policy could not be created.'),
          );
        },
      });
  }

  /** Extract the first human-readable message from a DRF error shape. */
  private apiMessage(error: unknown, fallback: string): string {
    const err = error as { error?: unknown };
    const data = err?.error as Record<string, unknown> | undefined;
    if (data && typeof data === 'object') {
      if (typeof data['detail'] === 'string') return data['detail'] as string;
      const nonField = data['non_field_errors'];
      if (Array.isArray(nonField) && nonField.length) {
        return String(nonField[0]);
      }
      for (const value of Object.values(data)) {
        if (Array.isArray(value) && value.length) return String(value[0]);
      }
    }
    return fallback;
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}
