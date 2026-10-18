/**
 * Shared types for the PayBlood landing demos.
 *
 * All records here are EXAMPLE data for the public landing. They are
 * explicitly labelled "demo" in the UI and never sent to the backend.
 * The evaluation logic is a local, deterministic simulation of the engine's
 * documented precedence — it is NOT the authoritative engine.
 */

export type DemoDecision = 'approved' | 'blocked' | 'escalated';

export interface DemoInvoice {
  id: string;
  vendor: string;
  number: string;
  amount: number;
  currency: string;
  dueDate: string | null;
  description: string;
}

export interface DemoPolicy {
  label: string;
  allowedCurrencies: string[];
  maxAmount: number;
  escalationThreshold: number;
  requireDueDate: boolean;
}

export interface ConditionResult {
  key: string;
  label: string;
  detail: string;
  passed: boolean;
}

export interface DemoOutcome {
  decision: DemoDecision;
  reasonCode: string;
  reasonDetail: string;
  conditions: ConditionResult[];
}

/** Currency coverage actually supported by the backend API (SUPPORTED_CURRENCIES). */
export interface Region {
  iso: string;
  country: string;
  /** Main country/area for the ISO 4217 code. */
  currency: string;
  /** Geographic pin on the world map. */
  lat: number;
  lng: number;
  /** Verified against the backend's SUPPORTED_CURRENCIES list. */
  supported: true;
  /** Real use inside the evaluation flow. */
  use: string;
  /** External data/banking sources. Always 'none' today — never invented. */
  source: string;
  /** Extra note, when available; displayed as optional detail. */
  detail?: string;
}