import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  ApprovalDecision,
  EvaluationResult,
  InvoiceSummary,
  InvoiceCreatePayload,
} from './invoices.models';

/**
 * Read-only invoice list for an organization.
 * The backend (GET /api/v1/organizations/{org}/invoices/) scopes the queryset
 * to the organization id from the URL; Django enforces organization isolation
 * and member permissions.
 */
@Injectable({ providedIn: 'root' })
export class InvoicesService {
  private readonly http = inject(HttpClient);

  list(orgId: string): Observable<InvoiceSummary[]> {
    return this.http.get<InvoiceSummary[]>(
      `${environment.apiBaseUrl}/organizations/${orgId}/invoices/`,
    );
  }

  /** One invoice by id, scoped to the organization by the backend. */
  get(orgId: string, invoiceId: string): Observable<InvoiceSummary> {
    return this.http.get<InvoiceSummary>(
      `${environment.apiBaseUrl}/organizations/${orgId}/invoices/${invoiceId}/`,
    );
  }

  /** Human approval/rejection (APPROVER). Returns the updated invoice. */
  decide(
    orgId: string,
    invoiceId: string,
    decision: ApprovalDecision,
    rationale?: string,
  ): Observable<InvoiceSummary> {
    return this.http.post<InvoiceSummary>(
      `${environment.apiBaseUrl}/organizations/${orgId}/invoices/${invoiceId}/approval/`,
      { decision, rationale },
    );
  }

  /**
   * Evaluate one received invoice against the active policy (OPERATOR or
   * FINANCE_ADMIN trigger; the deterministic engine decides the outcome).
   * Returns the engine result, never a human choice.
   */
  evaluate(orgId: string, invoiceId: string): Observable<EvaluationResult> {
    return this.http.post<EvaluationResult>(
      `${environment.apiBaseUrl}/organizations/${orgId}/invoices/${invoiceId}/evaluate/`,
      {},
    );
  }

  /** Read the recorded policy decision for one invoice (any active member). */
  decision(orgId: string, invoiceId: string): Observable<{
    result: string;
    reason_code: string;
    reason_detail: string;
    policy_version: number | null;
  }> {
    return this.http.get<{
      result: string;
      reason_code: string;
      reason_detail: string;
      policy_version: number | null;
    }>(`${environment.apiBaseUrl}/organizations/${orgId}/invoices/${invoiceId}/decision/`);
  }

  /** Create a new invoice from extracted/reviewed fields (extraction feature). */
  create(orgId: string, payload: InvoiceCreatePayload): Observable<InvoiceSummary> {
    return this.http.post<InvoiceSummary>(
      `${environment.apiBaseUrl}/organizations/${orgId}/invoices/`,
      payload,
    );
  }
}