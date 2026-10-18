import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { OrganizationSummary } from './organizations.models';

/**
 * Read-only organizations API access. The backend scopes the list to the
 * authenticated user's ACTIVE memberships; Django remains the authority.
 */
@Injectable({ providedIn: 'root' })
export class OrganizationsService {
  private readonly http = inject(HttpClient);

  list(): Observable<OrganizationSummary[]> {
    return this.http.get<OrganizationSummary[]>(
      `${environment.apiBaseUrl}/organizations/`,
    );
  }

  get(id: string): Observable<OrganizationSummary> {
    return this.http.get<OrganizationSummary>(
      `${environment.apiBaseUrl}/organizations/${id}/`,
    );
  }
}