import { CommonModule } from '@angular/common';
import { Component, OnDestroy, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import { Folio } from '../../shared/folio';
import { AuthService } from '../../core/auth/auth.service';
import { OrganizationsMembersService } from './organizations-members.service';
import { OrganizationsService } from './organizations.service';
import {
  GRANTABLE_ROLES,
  MemberInviteResult,
  MembershipSummary,
} from './organizations-members.models';

type LoadState = 'loading' | 'ready' | 'forbidden' | 'error';
type FormState = 'idle' | 'submitting' | 'error';
/** The setup-link panel states (token is never persisted, only in memory). */
type InviteState = 'hidden' | 'success' | 'failed' | 'regenerating' | 'regenerated';

/** Real link origin: the browser origin, so any device/host works. */
const fallbackOrigin = 'http://127.0.0.1:4200';

function setupLinkOrigin(): string {
  try {
    return window.location.origin;
  } catch {
    return fallbackOrigin;
  }
}

/** Build the full setup URL from the raw one-time token. */
function buildSetupLink(origin: string, token: string): string {
  return `${origin}/setup-account?token=${encodeURIComponent(token)}`;
}

/** Mask the token part of the link for on-screen display (Show/Hide). */
function maskToken(token: string): string {
  if (!token) return '';
  if (token.length <= 8) return '••••••••';
  return `${token.slice(0, 4)}••••${token.slice(-4)}`;
}

/**
 * Member administration for one organization (FINANCE_ADMIN only).
 *
 * Lists memberships, creates accounts (unusable password + optional one-time
 * setup invitation), adds existing accounts with an allowed role, changes
 * roles and toggles membership activity. The backend remains the authority:
 * every operation is audited, scoped to the URL organization, and rejects
 * FINANCE_ADMIN delegation or global flags.
 *
 * The password-setup link is a REAL URL built from the browser origin; the
 * raw token lives only in memory, is masked on screen by default, copied with
 * the full value, and cleared when the panel is closed. Regenerating the link
 * re-issues the one-time token through the existing audited invite endpoint
 * (which invalidates previous unused tokens), always with confirmation.
 */
@Component({
  selector: 'pb-organizations-members',
  imports: [CommonModule, Folio, RouterLink],
  templateUrl: './organizations-members.html',
  styleUrl: './organizations-members.scss',
})
export class OrganizationsMembersPage implements OnDestroy {
  protected readonly grantableRoles = GRANTABLE_ROLES;

  protected readonly state = signal<LoadState>('loading');
  protected readonly memberships = signal<MembershipSummary[]>([]);
  protected readonly organizationName = signal('');
  protected readonly isAdmin = signal(false);

  // Create-account form.
  protected readonly createEmail = signal('');
  protected readonly createRole = signal('OPERATOR');
  protected readonly createState = signal<FormState>('idle');
  protected readonly createError = signal('');
  /** The email of the just-created/focused account, shown in the panel. */
  protected readonly accountEmail = signal('');

  // Add-existing form.
  protected readonly addUserId = signal('');
  protected readonly addRole = signal('OPERATOR');
  protected readonly addState = signal<FormState>('idle');
  protected readonly addError = signal('');

  // Setup-link panel state.
  protected readonly inviteState = signal<InviteState>('hidden');
  protected readonly invite = signal<MemberInviteResult | null>(null);
  protected readonly inviteError = signal('');
  protected readonly linkVisible = signal(false);
  protected readonly copied = signal(false);
  protected readonly copyError = signal('');
  protected readonly invitingFor = signal<number | null>(null);
  /** Why the panel is open: right after creation vs from a row action. */
  protected readonly inviteReason = signal<'created' | 'issued'>('issued');
  /** Last user for whom a link was issued (kept for regeneration). */
  protected readonly lastInvitedUserId = signal<number | null>(null);
  protected readonly regenerating = signal(false);

  // Inline confirmation dialog for the row action (Cancel / Generate link).
  protected readonly issueConfirmOpen = signal(false);
  protected readonly issueConfirmEmail = signal('');
  protected readonly issueConfirmUserId = signal<number | null>(null);

  /** Memberships without the current actor's own row (no self-actions). */
  protected visibleMemberships(): MembershipSummary[] {
    const selfId = String(this.auth.user()?.id ?? '');
    if (!selfId) return this.memberships();
    return this.memberships().filter((m) => String(m.user.id) !== selfId);
  }

  private sub?: Subscription;
  private actionSub?: Subscription;

  constructor(
    private readonly api: OrganizationsMembersService,
    private readonly orgs: OrganizationsService,
    private readonly route: ActivatedRoute,
    private readonly auth: AuthService,
  ) {
    this.load();
  }

  private orgId(): string {
    return this.route.snapshot.paramMap.get('id') ?? '';
  }

  protected load(): void {
    this.sub?.unsubscribe();
    this.state.set('loading');
    const orgId = this.orgId();
    this.sub = this.api.list(orgId).subscribe({
      next: (memberships) => {
        this.memberships.set(memberships);
        const my = memberships.find(
          (m) => m.role === 'FINANCE_ADMIN' && m.is_active,
        );
        this.isAdmin.set(!!my);
        this.state.set('ready');
      },
      error: (error: { status?: number }) => {
        this.state.set(error.status === 403 || error.status === 404 ? 'forbidden' : 'error');
      },
    });
    this.orgs.get(orgId).subscribe({
      next: (org) => this.organizationName.set(org.name),
      error: () => {},
    });
  }

  /** Focuses and scrolls to the create-user form (used by the empty state). */
  protected focusCreate(): void {
    const el = document.getElementById('create_email');
    el?.scrollIntoView?.({ block: 'center' });
    el?.focus();
  }

  protected setCreateEmail(event: Event): void {
    this.createEmail.set((event.target as HTMLInputElement).value);
  }

  protected setCreateRole(event: Event): void {
    this.createRole.set((event.target as HTMLSelectElement).value);
  }

  protected async createAccount(): Promise<void> {
    const email = this.createEmail().trim().toLowerCase();
    if (!email || this.createState() === 'submitting') {
      this.createError.set('Review your input and try again.');
      return;
    }
    this.createState.set('submitting');
    this.createError.set('');
    this.actionSub = this.api
      .createAccount(this.orgId(), { email, role: this.createRole() })
      .subscribe({
        next: (result) => {
          this.createEmail.set('');
          this.createState.set('idle');
          this.accountEmail.set(result.email);
          this.load();
          // Issue the one-time setup link for the fresh account.
          this.inviteReason.set('created');
          this.requestInvite(result.id);
        },
        error: (error: { status?: number; error?: unknown }) => {
          this.createState.set('error');
          this.createError.set(this.createErrorMessage(error));
        },
      });
  }

  protected setAddUserId(event: Event): void {
    this.addUserId.set((event.target as HTMLInputElement).value);
  }

  protected setAddRole(event: Event): void {
    this.addRole.set((event.target as HTMLSelectElement).value);
  }

  protected async addExisting(): Promise<void> {
    const userId = Number(this.addUserId());
    if (!userId || Number.isNaN(userId)) {
      this.addError.set('A valid numeric user id is required.');
      return;
    }
    this.addState.set('submitting');
    this.addError.set('');
    this.actionSub = this.api
      .add(this.orgId(), { user: userId, role: this.addRole() })
      .subscribe({
        next: () => {
          this.addUserId.set('');
          this.addState.set('idle');
          this.load();
        },
        error: (error: { error?: unknown }) => {
          this.addState.set('error');
          this.addError.set(this.extractError(error));
        },
      });
  }

  /**
   * Row action: asks for confirmation, then issues a fresh personal link for
   * the selected membership. The backend invalidates previous unused tokens
   * for that user inside the same transaction, so the wording tells the
   * administrator the old link stops working.
   */
  protected issueSetupLink(membership: MembershipSummary): void {
    if (this.invitingFor() !== null) return; // already issuing
    this.issueConfirmEmail.set(membership.user.email || membership.user.username);
    this.issueConfirmUserId.set(membership.user.id);
    this.issueConfirmOpen.set(true);
  }

  protected cancelIssueConfirm(): void {
    this.issueConfirmOpen.set(false);
    this.issueConfirmUserId.set(null);
  }

  protected confirmIssueSetupLink(): void {
    const userId = this.issueConfirmUserId();
    if (userId === null || this.invitingFor() !== null) return;
    this.issueConfirmOpen.set(false);
    this.issueConfirmUserId.set(null);
    this.inviteReason.set('issued');
    this.requestInvite(userId);
  }

  private requestInvite(userId: number): void {
    this.invitingFor.set(userId);
    this.lastInvitedUserId.set(userId);
    this.inviteState.set('hidden');
    this.invite.set(null);
    this.inviteError.set('');
    this.copied.set(false);
    this.copyError.set('');
    this.linkVisible.set(false);
    this.actionSub = this.api.invite(this.orgId(), userId).subscribe({
      next: (result) => {
        this.invite.set(result);
        this.inviteState.set('success');
        this.invitingFor.set(null);
      },
      error: (error: { status?: number; error?: unknown }) => {
        this.inviteState.set('failed');
        this.inviteError.set(this.inviteErrorMessage(error));
        this.invitingFor.set(null);
      },
    });
  }

  /** Full setup URL (always the complete value, whatever the mask). */
  protected fullLink(): string {
    const invite = this.invite();
    if (!invite) return '';
    return buildSetupLink(setupLinkOrigin(), invite.setup_token);
  }

  /** Displayed value: real link, or masked token until "Show" is pressed. */
  protected displayedLink(): string {
    const invite = this.invite();
    if (!invite) return '';
    if (this.linkVisible()) return this.fullLink();
    const origin = setupLinkOrigin();
    return `${origin}/setup-account?token=${maskToken(invite.setup_token)}`;
  }

  protected toggleLinkVisible(): void {
    this.linkVisible.update((v) => !v);
    this.copied.set(false);
  }

  protected async copyLink(): Promise<void> {
    const value = this.fullLink();
    if (!value) return;
    this.copied.set(false);
    this.copyError.set('');
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(value);
        this.copied.set(true);
        return;
      } catch {
        // Fall through to the manual fallback below.
      }
    }
    this.copyError.set(
      'We could not copy the link automatically. You can show it and copy it ' +
        'manually.',
    );
  }

  /**
   * Closes the panel: clears the in-memory token and any transient copy state
   * so nothing usable lingers. Closing never triggers a new token request.
   */
  protected hideInvite(): void {
    this.invite.set(null);
    this.inviteState.set('hidden');
    this.inviteError.set('');
    this.copied.set(false);
    this.copyError.set('');
    this.linkVisible.set(false);
    this.invitingFor.set(null);
  }

  /** Confirms and re-issues the one-time link through the audited endpoint. */
  protected confirmRegenerate(): void {
    const invite = this.invite();
    if (!invite) return;
    if (this.regenerating()) return;
    const confirmed = window.confirm(
      'Generate a new link so the user can set their password? ' +
        'The previous link stops working if it is correctly revoked.',
    );
    if (!confirmed) return;
    this.regenerating.set(true);
    const userId = this.lastInvitedUserId();
    if (userId !== null) {
      this.actionSub = this.api.invite(this.orgId(), userId).subscribe({
        next: (result) => {
          this.invite.set(result);
          this.inviteState.set('regenerated');
          this.copied.set(false);
          this.linkVisible.set(false);
          this.regenerating.set(false);
        },
        error: (error: { status?: number; error?: unknown }) => {
          this.inviteState.set('failed');
          this.inviteError.set(this.inviteErrorMessage(error));
          this.regenerating.set(false);
        },
      });
    } else {
      this.regenerating.set(false);
    }
  }

  protected changeRole(membership: MembershipSummary, role: string): void {
    this.api.update(this.orgId(), membership.id, { role }).subscribe({
      next: () => this.load(),
      error: () => {},
    });
  }

  protected toggleActive(membership: MembershipSummary): void {
    const next = !membership.is_active;
    const confirmed = next
      ? true
      : window.confirm(
        `Deactivate ${membership.user.email} in this organization? Their history is preserved.`,
      );
    if (!confirmed) return;
    this.api.update(this.orgId(), membership.id, { is_active: next }).subscribe({
      next: () => this.load(),
      error: () => {},
    });
  }

  /** Maps the backend's real responses to the brief's user-facing texts. */
  protected createErrorMessage(error: { status?: number; error?: unknown }): string {
    const body = error.error;
    const detail =
      typeof body === 'string' ? body : (body as Record<string, unknown>)?.['detail'];
    // Backend field errors look like { email: ["A user with this email already exists."] }
    // so flatten field arrays too and search for the duplicate marker.
    const all =
      [detail, this.extractError(error)].filter((v) => typeof v === 'string').join(' ');
    if (all.toLowerCase().includes('already exists')) {
      return 'This email is already registered. You can link the existing account to this organization if you are authorized to do so.';
    }
    if (error.status === 403 || error.status === 404) {
      return 'You do not have permission to create users in this organization.';
    }
    if (error.status === 400) {
      return 'Review your input and try again.';
    }
    return 'We could not create the user. Try again. If the problem continues, contact an administrator.';
  }

  protected inviteErrorMessage(error: { status?: number; error?: unknown }): string {
    if (error.status === 403 || error.status === 404) {
      return 'You do not have permission to perform this operation.';
    }
    return 'We could not generate the setup link. The account exists, but the user cannot complete the initial setup yet. Try again with the authorized operation.';
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

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.actionSub?.unsubscribe();
  }
}