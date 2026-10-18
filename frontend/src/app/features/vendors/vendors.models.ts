/** Real contracts of the vendors API (backend VendorSerializer). */

export type VendorStatus = 'active' | 'inactive';

/** Organization ownership embedded by the backend in every vendor payload. */
export interface VendorOrganizationRef {
  id: string;
  name: string;
  status: 'active' | 'inactive';
}

/** One vendor as returned by the backend (read representation). */
export interface VendorSummary {
  id: string;
  organization: VendorOrganizationRef;
  legal_name: string;
  tax_id: string;
  status: VendorStatus;
  created_at: string;
  updated_at: string;
}

/**
 * Payload for POST /vendors/ (backend VendorCreateSerializer).
 * Only legal_name and tax_id are writable; status defaults to active
 * server-side and organization ownership comes from the URL.
 */
export interface VendorCreatePayload {
  legal_name: string;
  tax_id: string;
}

/**
 * Payload for PATCH /vendors/{id}/ (backend VendorUpdateSerializer).
 * status is deliberately NOT writable here — activation/deactivation are
 * explicit, separately authorized operations.
 */
export interface VendorUpdatePayload {
  legal_name?: string;
  tax_id?: string;
}
