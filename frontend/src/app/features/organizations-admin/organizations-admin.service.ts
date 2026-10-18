import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  GlobalCandidateUser,
  GlobalOrganization,
  GlobalOrganizationCreateInput,
  GlobalOrganizationCreateResult,
  GlobalOrganizationUpdateInput,
} from './organizations-admin.models';

/**
 * Superuser-only global organization administration API.
 * Django remains the authority on every call: the endpoints re-check
 * is_superuser server-side, and this service never receives global
 * privilege fields from the client.
 */
@Injectable({ providedIn: 'root' })
export class OrganizationsAdminService {
  private readonly http = inject(HttpClient);

  private api(path: string) {
    return `${environment.apiBaseUrl}/${path}`;
  }

  list(): Observable<GlobalOrganization[]> {
    return this.http.get<GlobalOrganization[]>(this.api('admin/organizations/'));
  }

  retrieve(id: string): Observable<GlobalOrganization> {
    return this.http.get<GlobalOrganization>(
      this.api(`admin/organizations/${id}/`),
    );
  }

  create(
    input: GlobalOrganizationCreateInput,
  ): Observable<GlobalOrganizationCreateResult> {
    return this.http.post<GlobalOrganizationCreateResult>(
      this.api('admin/organizations/'),
      input,
    );
  }

  update(
    id: string,
    input: GlobalOrganizationUpdateInput,
  ): Observable<GlobalOrganization> {
    return this.http.patch<GlobalOrganization>(
      this.api(`admin/organizations/${id}/`),
      input,
    );
  }

  listUsers(q: string): Observable<GlobalCandidateUser[]> {
    return this.http.get<GlobalCandidateUser[]>(
      this.api(`admin/users/?q=${encodeURIComponent(q)}`),
    );
  }
}