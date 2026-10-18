/**
 * Vendors API access (Slice 3 contract).
 *
 * Reads (list/retrieve) are open to any active member of the active
 * organization; mutations (create, update, activate, deactivate) are
 * reserved for FINANCE_ADMIN. The backend remains the authority: it scopes
 * every query to the URL organization, normalizes tax identifiers, and
 * enforces the writable-field allowlists.
 */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  VendorCreatePayload,
  VendorSummary,
  VendorUpdatePayload,
} from './vendors.models';

@Injectable({ providedIn: 'root' })
export class VendorsService {
  private readonly http = inject(HttpClient);

  list(orgId: string): Observable<VendorSummary[]> {
    return this.http.get<VendorSummary[]>(
      `${environment.apiBaseUrl}/organizations/${orgId}/vendors/`,
    );
  }

  get(orgId: string, vendorId: string): Observable<VendorSummary> {
    return this.http.get<VendorSummary>(
      `${environment.apiBaseUrl}/organizations/${orgId}/vendors/${vendorId}/`,
    );
  }

  create(orgId: string, payload: VendorCreatePayload): Observable<VendorSummary> {
    return this.http.post<VendorSummary>(
      `${environment.apiBaseUrl}/organizations/${orgId}/vendors/`,
      payload,
    );
  }

  /** PATCH business data only (legal_name and/or tax_id); never status. */
  update(
    orgId: string,
    vendorId: string,
    payload: VendorUpdatePayload,
  ): Observable<VendorSummary> {
    return this.http.patch<VendorSummary>(
      `${environment.apiBaseUrl}/organizations/${orgId}/vendors/${vendorId}/`,
      payload,
    );
  }

  activate(orgId: string, vendorId: string): Observable<VendorSummary> {
    return this.http.post<VendorSummary>(
      `${environment.apiBaseUrl}/organizations/${orgId}/vendors/${vendorId}/activate/`,
      {},
    );
  }

  deactivate(orgId: string, vendorId: string): Observable<VendorSummary> {
    return this.http.post<VendorSummary>(
      `${environment.apiBaseUrl}/organizations/${orgId}/vendors/${vendorId}/deactivate/`,
      {},
    );
  }
}
