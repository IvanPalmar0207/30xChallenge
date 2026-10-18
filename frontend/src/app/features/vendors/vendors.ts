import { CommonModule } from '@angular/common';
import { Component, OnDestroy, signal, type Signal, inject } from '@angular/core';
import { toObservable } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Subscription, take } from 'rxjs';

import { Folio } from '../../shared/folio';
import { Icon } from '../../shared/icon';
import { AuthService } from '../../core/auth/auth.service';
import { CapabilitiesService } from '../../core/auth/capabilities.service';
import { UserProfile } from '../../core/auth/models';
import { VendorsService } from './vendors.service';
import { VendorStatus, VendorSummary } from './vendors.models';

type LoadState = 'loading' | 'ready' | 'forbidden' | 'error' | 'noorganization';
type FormMode = 'create' | 'edit';

const STATUS_LABEL: Record<VendorStatus, string> = {
  active: 'active',
  inactive: 'inactive',
};

/**
 * Vendors — supplier registry wired to the real backend.
 *
 * Reads are open to any active member; mutations (create, update, explicit
 * activate/deactivate) are FINANCE_ADMIN-only, and the backend remains the
 * authority: it normalizes tax identifiers and enforces every permission on
 * each request. `status` is never writable through the ordinary update —
 * activation/deactivation are the two explicit operations shown here.
 */
@Component({
  selector: 'pb-vendors',
  imports: [CommonModule, FormsModule, Folio, Icon],
  templateUrl: './vendors.html',
  styleUrl: './vendors.scss',
})
export class VendorsPage implements OnDestroy {
  protected readonly user!: Signal<UserProfile | null>;
  protected readonly state = signal<LoadState>('loading');
  protected readonly vendors = signal<VendorSummary[]>([]);
  protected readonly orgName = signal('—');

  // Form state (create/edit editor panel).
  protected readonly formMode = signal<FormMode | null>(null);
  protected readonly editing = signal<VendorSummary | null>(null);
  protected readonly legalName = signal('');
  protected readonly taxId = signal('');
  protected readonly submitting = signal(false);
  protected readonly formError = signal('');
  protected readonly actionError = signal('');

  private sub?: Subscription;
  private readonly user$ = toObservable(this.user);
  private orgId?: string;

  protected readonly cap = inject(CapabilitiesService);

  constructor(
    private readonly service: VendorsService,
    private readonly auth: AuthService,
  ) {
    this.user = this.auth.user;
    // Same load pattern as the invoices page: if the user profile is already
    // populated, load immediately; otherwise wait for the restoration signal.
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
        this.vendors.set(rows);
        this.state.set('ready');
      },
      error: (error: { status?: number }) => {
        this.state.set(error.status === 403 ? 'forbidden' : 'error');
      },
    });
  }

  protected statusLabel(status: VendorStatus): string {
    return STATUS_LABEL[status] ?? status;
  }

  protected isAdmin(): boolean {
    return this.cap.canManageVendors();
  }

  // ── create / edit workflows ──────────────────────────────────────────────

  protected openCreate(): void {
    this.formMode.set('create');
    this.editing.set(null);
    this.legalName.set('');
    this.taxId.set('');
    this.formError.set('');
  }

  protected openEdit(vendor: VendorSummary): void {
    this.formMode.set('edit');
    this.editing.set(vendor);
    this.legalName.set(vendor.legal_name);
    this.taxId.set(vendor.tax_id);
    this.formError.set('');
  }

  protected closeForm(): void {
    this.formMode.set(null);
    this.editing.set(null);
    this.formError.set('');
  }

  protected canSubmit(): boolean {
    return (
      !this.submitting() &&
      this.legalName().trim().length > 0 &&
      this.taxId().trim().length > 0
    );
  }

  /**
   * Submit create or edit. The payload mirrors the backend's conservative
   * normalization (strip + uppercase) so the user sees the stored form
   * immediately; the API re-normalizes and remains the authority.
   */
  protected submit(): void {
    if (!this.orgId || !this.canSubmit()) return;
    const mode = this.formMode();
    this.submitting.set(true);
    this.formError.set('');

    // The concrete object type is assignable to both the create and the
    // update payloads (the update variant's fields are optional).
    const payload = {
      legal_name: this.legalName().trim(),
      tax_id: this.taxId().trim().toUpperCase(),
    };
    const request =
      mode === 'edit' && this.editing()
        ? this.service.update(this.orgId, this.editing()!.id, payload)
        : this.service.create(this.orgId, payload);

    request.subscribe({
      next: () => {
        this.submitting.set(false);
        this.closeForm();
        this.load(); // refresh from the server, which is authoritative
      },
      error: (error) => {
        this.submitting.set(false);
        this.formError.set(
          this.apiMessage(error, 'The vendor could not be saved.'),
        );
      },
    });
  }

  /** Explicit activate/deactivate (never a delete). */
  protected toggleStatus(vendor: VendorSummary): void {
    if (!this.orgId || this.submitting()) return;
    const activate = vendor.status === 'inactive';
    this.submitting.set(true);
    this.actionError.set('');
    const request = activate
      ? this.service.activate(this.orgId, vendor.id)
      : this.service.deactivate(this.orgId, vendor.id);
    request.subscribe({
      next: () => {
        this.submitting.set(false);
        this.load();
      },
      error: (error) => {
        this.submitting.set(false);
        this.actionError.set(
          this.apiMessage(
            error,
            `The vendor could not be ${activate ? 'activated' : 'deactivated'}.`,
          ),
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
