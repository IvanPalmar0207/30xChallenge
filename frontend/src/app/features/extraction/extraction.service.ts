/**
 * Service for invoice extraction (Slice 7).
 * Handles calls to the backend extraction endpoint and vendor listing.
 */
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ExtractionResult, VendorSummary } from './extraction.models';

@Injectable({ providedIn: 'root' })
export class ExtractionService {
  constructor(private http: HttpClient) {}

  /**
   * Upload a file (PDF, JPEG, PNG) to the extraction endpoint.
   * Returns the extracted fields and verification status.
   */
  extract(orgId: string, file: File): Observable<ExtractionResult> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<ExtractionResult>(
      `${environment.apiBaseUrl}/organizations/${orgId}/extraction/`,
      formData,
    );
  }

  /**
   * List all vendors in an organization (for dropdown population).
   * Used by the extraction form to let users select the vendor after review.
   */
  listVendors(orgId: string): Observable<VendorSummary[]> {
    return this.http.get<VendorSummary[]>(
      `${environment.apiBaseUrl}/organizations/${orgId}/vendors/`,
    );
  }
}
