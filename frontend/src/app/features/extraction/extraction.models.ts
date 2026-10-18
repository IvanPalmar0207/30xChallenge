/**
 * Models for AI-assisted invoice extraction (Slice 7).
 */

/** A single extracted invoice field with confidence and validation results. */
export interface ExtractedField {
  value: string | null;
  evidence: string | null;  // The text snippet from the document supporting this field
  confidence: 'medium' | 'low' | 'absent';  // medium = value + evidence; low = value only; absent = null
  validation_errors: string[];
}

/** Complete extraction result with all fields, metadata, and verification status. */
export interface ExtractionResult {
  extraction_id: string;
  provider_used: string;
  model_used: string;
  verification_status: 'not_configured' | 'passed' | 'warnings' | 'failed' | 'partial';
  verification_message: string;
  raw_text_extracted: boolean;
  fields: Record<string, ExtractedField>;
  cross_field_errors: string[];
  warnings: string[];
}

/** Minimal vendor info for dropdown and auto-selection. */
export interface VendorSummary {
  id: string;
  legal_name: string;
  tax_id: string | null;
  status: 'active' | 'inactive';
}

/** Payload sent to /organizations/{org}/invoices/ to create an invoice. */
export interface InvoiceCreatePayload {
  vendor: string;  // UUID
  invoice_number: string;
  issue_date: string;  // YYYY-MM-DD
  due_date?: string | null;  // YYYY-MM-DD, optional
  amount: string;  // decimal string
  currency: string;  // uppercase, e.g., 'USD'
  description?: string | null;
}

/** Invoice created in response to invoice creation. */
export interface InvoiceSummary {
  id: string;
  vendor: string;
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

export type InvoiceStatus =
  | 'draft'
  | 'registered'
  | 'evaluated'
  | 'escalated'
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'paid';
