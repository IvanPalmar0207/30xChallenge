import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  MemberAccountCreatePayload,
  MemberAddPayload,
  MemberInviteResult,
  MembershipSummary,
  MemberUpdatePayload,
} from './organizations-members.models';

/**
 * Organization-scoped member administration (FINANCE_ADMIN only).
 * Wraps the existing audited endpoints; Django re-checks authority and scopes
 * every query to the URL organization. Clients never send global flags.
 */
@Injectable({ providedIn: 'root' })
export class OrganizationsMembersService {
  private readonly http = inject(HttpClient);

  private api(orgId: string, path: string) {
    return `${environment.apiBaseUrl}/organizations/${orgId}/${path}`;
  }

  list(orgId: string): Observable<MembershipSummary[]> {
    return this.http.get<MembershipSummary[]>(this.api(orgId, 'memberships/'));
  }

  /** Adds an existing account to the organization with an allowed role. */
  add(orgId: string, payload: MemberAddPayload): Observable<MembershipSummary> {
    return this.http.post<MembershipSummary>(this.api(orgId, 'memberships/'), payload);
  }

  /** Creates a brand-new account + first membership atomically. */
  createAccount(
    orgId: string,
    payload: MemberAccountCreatePayload,
  ): Observable<{ id: number; email: string; role: string; membership_id: string }> {
    return this.http.post<{
      id: number;
      email: string;
      role: string;
      membership_id: string;
    }>(this.api(orgId, 'users/'), payload);
  }

  update(
    orgId: string,
    membershipId: string,
    payload: MemberUpdatePayload,
  ): Observable<MembershipSummary> {
    return this.http.patch<MembershipSummary>(
      this.api(orgId, `memberships/${membershipId}/`),
      payload,
    );
  }

  /** Issues a one-time setup token; shown to the admin exactly once. */
  invite(orgId: string, userId: number): Observable<MemberInviteResult> {
    return this.http.post<MemberInviteResult>(
      this.api(orgId, `users/${userId}/invite/`),
      {},
    );
  }
}