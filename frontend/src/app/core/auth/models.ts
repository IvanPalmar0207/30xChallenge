/**
 * Typed contracts for the PayBlood JWT auth API. Field names mirror the
 * real backend responses (verified against apps/accounts).
 */

export interface MembershipSummary {
  organization_id: string;
  organization_name: string;
  role: 'FINANCE_ADMIN' | 'OPERATOR' | 'APPROVER' | 'AUDITOR';
}

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  memberships?: MembershipSummary[];
  /** Derived from the session's Django superuser status; UI visibility only —
   *  every global administration endpoint re-checks server-side. */
  is_global_admin?: boolean;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: UserProfile;
}

export interface RefreshResponse {
  access: string;
  refresh?: string; // present when rotation is on
}

export type AuthStatus = 'restoring' | 'authed' | 'guest';