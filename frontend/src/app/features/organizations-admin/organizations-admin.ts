import { CommonModule } from '@angular/common';
import { Component, OnDestroy, signal } from '@angular/core';
import { Subscription } from 'rxjs';

import { Folio } from '../../shared/folio';
import { OrganizationsAdminService } from './organizations-admin.service';
import {
  GlobalCandidateUser,
  GlobalOrganization,
  GlobalOrganizationCreateResult,
} from './organizations-admin.models';

type LoadState = 'loading' | 'ready' | 'forbidden' | 'error';
type FormState = 'idle' | 'submitting' | 'success' | 'error';

/**
 * Global organization administration (superuser only).
 *
 * Lists every organization, creates a new one with its initial FINANCE_ADMIN,
 * and toggles administrative fields (name/status) with explicit confirmation.
 * The backend re-checks superuser authority on every request; this page only
 * renders it when the session profile says is_global_admin. The one-time
 * setup token for a freshly created account is shown exactly once here.
 */
@Component({
  selector: 'pb-organizations-admin',
  imports: [CommonModule, Folio],
  templateUrl: './organizations-admin.html',
  styleUrl: './organizations-admin.scss',
})
export class OrganizationsAdminPage implements OnDestroy {
  protected readonly state = signal<LoadState>('loading');
  protected readonly organizations = signal<GlobalOrganization[]>([]);

  protected readonly formState = signal<FormState>('idle');
  protected readonly formError = signal('');
  protected readonly created = signal<GlobalOrganizationCreateResult | null>(null);

  // Create-form model.
  protected readonly name = signal('');
  protected readonly adminEmail = signal('');
  protected readonly candidates = signal<GlobalCandidateUser[]>([]);
  protected readonly candidatesLoading = signal(false);
  protected readonly setupTokenShown = signal(false);

  private sub?: Subscription;
  private createSub?: Subscription;

  constructor(private readonly api: OrganizationsAdminService) {
    this.load();
  }

  protected load(): void {
    this.sub?.unsubscribe();
    this.state.set('loading');
    this.sub = this.api.list().subscribe({
      next: (orgs) => {
        this.organizations.set(orgs);
        this.state.set('ready');
      },
      error: (error: { status?: number }) => {
        this.state.set(error.status === 403 || error.status === 404 ? 'forbidden' : 'error');
      },
    });
  }

  protected setName(event: Event): void {
    this.name.set((event.target as HTMLInputElement).value);
  }

  protected setAdminEmail(event: Event): void {
    this.adminEmail.set((event.target as HTMLInputElement).value);
    this.searchCandidates();
  }

  protected searchCandidates(): void {
    this.candidatesLoading.set(true);
    this.candidates.set([]);
    const q = this.adminEmail().trim();
    if (q.length < 3) {
      this.candidatesLoading.set(false);
      return;
    }
    // Read-only candidate lookup; the form accepts any valid email even if
    // no match is returned (the account is created on submit when missing).
    const sub = this.api.listUsers(q).subscribe({
      next: (candidates) => {
        this.candidates.set(candidates);
        this.candidatesLoading.set(false);
      },
      error: () => {
        this.candidatesLoading.set(false);
      },
    });
    this.candidatesLoadingSub(sub);
  }

  protected selectCandidate(user: GlobalCandidateUser): void {
    this.adminEmail.set(user.username);
    this.candidates.set([]);
  }

  private candidatesLoadingSub(sub: Subscription): void {
    this.createSub?.unsubscribe();
    this.createSub = sub;
  }

  protected async submit(): Promise<void> {
    const name = this.name().trim();
    const adminEmail = this.adminEmail().trim().toLowerCase();
    if (!name || !adminEmail || this.formState() === 'submitting') {
      this.formError.set('Both the organization name and the admin email are required.');
      return;
    }
    this.formState.set('submitting');
    this.formError.set('');
    this.created.set(null);
    this.setupTokenShown.set(false);
    this.createSub = this.api
      .create({ name, admin_email: adminEmail })
      .subscribe({
        next: (result) => {
          this.created.set(result);
          this.formState.set('success');
          this.name.set('');
          this.adminEmail.set('');
          this.candidates.set([]);
          this.load();
        },
        error: (error: { error?: unknown; status?: number }) => {
          this.formState.set('error');
          this.formError.set(this.extractError(error));
        },
      });
  }

  protected toggleStatus(org: GlobalOrganization): void {
    const next = org.status === 'active' ? 'inactive' : 'active';
    // Activation is safe and explicit; deactivation requires confirmation.
    const confirmed = next === 'inactive'
      ? window.confirm(
        `Deactivate "${org.name}"? Members lose access until it is reactivated.`,
      )
      : true;
    if (!confirmed) return;

    this.api.update(org.id, { status: next }).subscribe({
      next: () => this.load(),
      error: (error: { error?: unknown }) => {
        this.formState.set('error');
        this.formError.set(this.extractError(error));
      },
    });
  }

  protected extractError(error: { error?: unknown }): string {
    const body = error.error;
    if (typeof body === 'string' && body.trim()) return body;
    if (body && typeof body === 'object') {
      for (const key of ['detail', 'message', 'error']) {
        const value = (body as Record<string, unknown>)[key];
        if (typeof value === 'string' && value.trim()) return value;
      }
      const fieldMessages = Object.entries(body as Record<string, unknown>)
        .filter(([key]) => !['detail', 'message', 'error'].includes(key))
        .flatMap(([key, value]) => this.flatten(value).map((m: string) => `${key}: ${m}`));
      if (fieldMessages.length) return fieldMessages.join(' · ');
    }
    return 'The server could not complete the operation.';
  }

  private flatten(value: unknown, out: string[] = []): string[] {
    if (typeof value === 'string') out.push(value);
    else if (Array.isArray(value)) value.forEach((entry) => this.flatten(entry, out));
    else if (value && typeof value === 'object') {
      Object.values(value).forEach((entry) => this.flatten(entry, out));
    }
    return out;
  }

  protected canSubmit(): boolean {
    return (
      this.name().trim().length > 0 &&
      this.adminEmail().trim().length > 0 &&
      this.formState() !== 'submitting'
    );
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.createSub?.unsubscribe();
  }
}