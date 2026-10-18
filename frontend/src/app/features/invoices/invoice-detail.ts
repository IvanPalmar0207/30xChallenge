import { CommonModule } from '@angular/common';
import { Component, computed, OnInit, signal, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import { Folio } from '../../shared/folio';
import { Icon } from '../../shared/icon';
import { AuthService } from '../../core/auth/auth.service';
import { CapabilitiesService } from '../../core/auth/capabilities.service';
import { InvoicesService } from './invoices.service';
import {
  ApprovalDecision,
  EvaluationResult,
  InvoiceStatus,
  InvoiceSummary,
} from './invoices.models';

type LoadState = 'loading' | 'ready' | 'forbidden' | 'notfound' | 'error';

/** Static explanation per state, aligned with the backend contract. */
const STATUS_NOTE: Record<InvoiceStatus, string> = {
  received:
    'Received and registered. It has not been evaluated against the active policy yet.',
  pending_approval:
    'The policy engine escalated this invoice for human review. It awaits an APPROVER decision.',
  approved:
    'Approved (by the deterministic engine or by an APPROVER). PayBlood never executes payments.',
  blocked:
    'Blocked: the active policy reports a mandatory rule violation.',
  escalated:
    'Escalated: the engine could not decide safely and the invoice needs human review.',
  rejected: 'Rejected by an APPROVER.',
};

/**
 * Invoice detail — reads a real invoice via the organization-scoped detail
 * endpoint and exposes only backend-supported actions:
 *
 * - `received` + OPERATOR/FINANCE_ADMIN  → "Evaluate invoice" triggers the
 *   deterministic policy engine (POST .../evaluate/); the engine decides, and
 *   the real result + reason are shown.
 * - `pending_approval` + APPROVER → Approve/Reject (human decision).
 * - Any other state/role combination shows the state explanation with no
 *   invalid transitions. The backend remains the authority.
 */
@Component({
  selector: 'pb-invoice-detail',
  imports: [CommonModule, Folio, Icon, RouterLink],
  templateUrl: './invoice-detail.html',
  styleUrl: './invoice-detail.scss',
})
export class InvoiceDetailPage implements OnInit {
  protected readonly state = signal<LoadState>('loading');
  protected readonly invoice = signal<InvoiceSummary | null>(null);
  protected readonly orgName = signal('—');
  protected readonly acting = signal(false);
  protected readonly actionError = signal('');
  protected readonly evaluationResult = signal<EvaluationResult | null>(null);
  protected readonly decisionReason = signal<string | null>(null);
  protected readonly decisionPolicyVersion = signal<number | null>(null);

  private sub?: Subscription;
  private orgId?: string;
  private invoiceId?: string;

  protected readonly cap = inject(CapabilitiesService);

  /** APPROVER in the active organization. */
  protected readonly isApprover = computed(() => this.cap.canApproveInvoice());
  /** OPERATOR/FINANCE_ADMIN in the active organization (engine trigger). */
  protected readonly isEvaluator = computed(() => this.cap.canEvaluateInvoice());

  constructor(
    private readonly route: ActivatedRoute,
    private readonly service: InvoicesService,
    private readonly auth: AuthService,
  ) {}

  ngOnInit(): void {
    this.orgId = this.auth.currentMembership()?.organization_id;
    const organizationName = this.auth.currentMembership()?.organization_name;
    this.invoiceId = this.route.snapshot.paramMap.get('id') ?? undefined;
    if (!this.orgId || !this.invoiceId) {
      this.state.set('notfound');
      return;
    }
    this.orgName.set(organizationName ?? '—');
    this.load();
  }

  /** Human approval: only an APPROVER may act on a pending_approval invoice. */
  protected canAct(): boolean {
    return this.isApprover() && this.invoice()?.status === 'pending_approval';
  }

  /** Engine evaluation: only OPERATOR/FINANCE_ADMIN on a received invoice. */
  protected canEvaluate(): boolean {
    return this.isEvaluator() && this.invoice()?.status === 'received';
  }

  protected statusNote(status: InvoiceStatus): string {
    return STATUS_NOTE[status] ?? status;
  }

  private load(): void {
    if (!this.orgId || !this.invoiceId) return;
    this.sub?.unsubscribe();
    this.state.set('loading');
    this.decisionReason.set(null);
    this.decisionPolicyVersion.set(null);
    this.sub = this.service.get(this.orgId, this.invoiceId).subscribe({
      next: (invoice) => {
        this.invoice.set(invoice);
        this.state.set('ready');
        // Evaluated invoices expose their recorded engine reason; missing or
        // unavailable decisions do not block the page.
        if (invoice.status !== 'received') {
          this.loadDecision();
        }
      },
      error: (error: { status?: number }) => {
        this.state.set(
          error.status === 403 ? 'forbidden' : error.status === 404 ? 'notfound' : 'error',
        );
      },
    });
  }

  private loadDecision(): void {
    if (!this.orgId || !this.invoiceId) return;
    this.service.decision(this.orgId, this.invoiceId).subscribe({
      next: (decision) => {
        this.decisionReason.set(decision.reason_detail);
        this.decisionPolicyVersion.set(decision.policy_version);
      },
      // 404 (no recorded decision) and network errors leave the explanation
      // empty; the state badge and static note still render.
      error: () => undefined,
    });
  }

  /** Trigger the deterministic engine on a received invoice. */
  protected evaluate(): void {
    if (!this.orgId || !this.invoiceId || this.acting()) return;
    this.acting.set(true);
    this.actionError.set('');
    this.service.evaluate(this.orgId, this.invoiceId).subscribe({
      next: (result) => {
        this.evaluationResult.set(result);
        this.acting.set(false);
        // The engine transitioned the status (escalated → pending_approval,
        // approved/blocked stay as the engine decided). Refresh the invoice
        // so the UI shows the real state without the loading skeleton.
        this.refresh();
      },
      error: (error: { status?: number; error?: { detail?: string } }) => {
        this.acting.set(false);
        if (error.status === 409) {
          this.actionError.set('This invoice was already evaluated. Reloading…');
          this.refresh();
        } else if (error.status === 403) {
          this.actionError.set('You are not allowed to evaluate this invoice.');
        } else if (error.status === 400) {
          this.actionError.set(error.error?.detail ?? 'This invoice cannot be evaluated.');
        } else {
          this.actionError.set('The evaluation could not be completed. Try again.');
        }
      },
    });
  }

  /** Re-fetch the invoice without flipping the page into the skeleton state. */
  private refresh(): void {
    if (!this.orgId || !this.invoiceId) return;
    this.service.get(this.orgId, this.invoiceId).subscribe({
      next: (invoice) => {
        this.invoice.set(invoice);
        if (invoice.status !== 'received') {
          this.loadDecision();
        }
      },
      error: () => undefined,
    });
  }

  protected decide(decision: ApprovalDecision): void {
    if (!this.orgId || !this.invoiceId || this.acting()) return;
    this.acting.set(true);
    this.actionError.set('');
    this.service.decide(this.orgId, this.invoiceId, decision).subscribe({
      next: (updated) => {
        this.invoice.set(updated);
        this.acting.set(false);
      },
      error: (error: { status?: number; error?: { detail?: string } }) => {
        this.acting.set(false);
        if (error.status === 409) {
          // The invoice was already decided elsewhere — reload to avoid stale UI.
          this.actionError.set('This invoice was already decided. Reloading…');
          this.load();
        } else if (error.status === 403) {
          this.actionError.set('You are not allowed to decide this invoice.');
        } else if (error.status === 400) {
          this.actionError.set(error.error?.detail ?? 'This invoice is no longer pending approval.');
        } else {
          this.actionError.set('The decision could not be saved. Try again.');
        }
      },
    });
  }

  protected approve(): void {
    this.decide('approved');
  }

  protected reject(): void {
    this.decide('rejected');
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}
