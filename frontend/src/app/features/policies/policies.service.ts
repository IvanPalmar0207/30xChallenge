/**
 * Policies API access (Slice 6 contract).
 *
 * Reads (list/retrieve of policy versions) are open to any active member;
 * creation is FINANCE_ADMIN-only. Versions are immutable: the backend offers
 * no update or delete endpoints. The policy engine remains solely
 * responsible for financial evaluation — this service only reads and
 * creates the rule versions.
 */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { PolicyCreatePayload, PolicyVersion } from './policies.models';

@Injectable({ providedIn: 'root' })
export class PoliciesService {
  private readonly http = inject(HttpClient);

  /** All policy versions of the organization, newest first (backend order). */
  list(orgId: string): Observable<PolicyVersion[]> {
    return this.http.get<PolicyVersion[]>(
      `${environment.apiBaseUrl}/organizations/${orgId}/policies/`,
    );
  }

  get(orgId: string, policyId: string): Observable<PolicyVersion> {
    return this.http.get<PolicyVersion>(
      `${environment.apiBaseUrl}/organizations/${orgId}/policies/${policyId}/`,
    );
  }

  /** Create a new policy version; the backend deactivates the previous one. */
  create(orgId: string, payload: PolicyCreatePayload): Observable<PolicyVersion> {
    return this.http.post<PolicyVersion>(
      `${environment.apiBaseUrl}/organizations/${orgId}/policies/`,
      payload,
    );
  }
}
