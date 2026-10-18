/** Real contracts of the policies API (backend PolicySerializer). */

/** One immutable policy version as returned by the backend. */
export interface PolicyVersion {
  id: string;
  version: number;
  is_active: boolean;
  /** [] means no currency restriction (backend semantics). */
  allowed_currencies: string[];
  /** Hard cap: exceeding it blocks. null = no cap. */
  max_amount: string | null;
  /** Above it escalates (if not blocked first). null = no threshold. */
  escalation_threshold: string | null;
  require_due_date: boolean;
  require_description: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * Payload for POST /policies/ (backend PolicyCreateSerializer).
 * Creating a new version deactivates the previous one (one active policy
 * per organization). Fields are optional: defaults mirror the serializer
 * (allowed_currencies=[], max_amount/threshold null, flags false).
 */
export interface PolicyCreatePayload {
  allowed_currencies: string[];
  max_amount: string | null;
  escalation_threshold: string | null;
  require_due_date: boolean;
  require_description: boolean;
}
