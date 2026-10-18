/**
 * Real contracts of the organization-scoped member administration API
 * (FINANCE_ADMIN only; backend is the authority).
 */

export type OrgRole = 'FINANCE_ADMIN' | 'OPERATOR' | 'APPROVER' | 'AUDITOR';

/** Roles that may be delegated to ordinary members (server allowlist). */
export const GRANTABLE_ROLES = ['OPERATOR', 'APPROVER', 'AUDITOR'] as const;

export interface MemberUser {
  id: number;
  username: string;
  email: string;
}

export interface MembershipSummary {
  id: string;
  user: MemberUser;
  role: OrgRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Payload for creating a brand-new account + first membership. */
export interface MemberAccountCreatePayload {
  email: string;
  role: string;
}

/** Payload for adding an existing account to this organization. */
export interface MemberAddPayload {
  user: number;
  role: string;
}

/** Payload for role/membership updates (partial). */
export interface MemberUpdatePayload {
  role?: string;
  is_active?: boolean;
}

/** Response of the invite endpoint (the raw token is shown exactly once). */
export interface MemberInviteResult {
  setup_token: string;
  expires_at: string;
}