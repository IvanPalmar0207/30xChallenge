/** Real contracts for invoice list from the backend serializer. */

export interface InvoiceVendorRef {
  id: string;
  legal_name: string;
  tax_id: string;
}

export type InvoiceStatus = 'received' | 'pending_approval' | 'approved' | 'blocked' | 'escalated' | 'rejected';

export interface InvoiceSummary {
  id: string;
  vendor: InvoiceVendorRef;
  invoice_number: string;
  issue_date: string;
  due_date: string | null;
  amount: string;
  currency: string;
  description: string;
  status: InvoiceStatus;
  created_at: string;
  updated_at: string;
}
/** Human decision outcomes accepted by the approval endpoint. */
export type ApprovalDecision = 'approved' | 'rejected';

/** Result of POST /organizations/{org}/invoices/{id}/evaluate/. */
export interface EvaluationResult {
  invoice_id: string;
  result: 'approved' | 'blocked' | 'escalated';
  reason_code: string;
  reason_detail: string;
  policy_version: number | null;
}

/** Payload sent to POST /organizations/{org}/invoices/ to create an invoice. */
export interface InvoiceCreatePayload {
  vendor: string;  // UUID
  invoice_number: string;
  issue_date: string;  // YYYY-MM-DD
  due_date?: string | null;  // YYYY-MM-DD, optional
  amount: string;  // decimal string
  currency: string;  // uppercase, e.g., 'USD'
  description?: string | null;
}
