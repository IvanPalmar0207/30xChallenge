/** Real contracts of the global admin API (superuser only). */

export interface GlobalOrganization {
  id: string;
  name: string;
  status: 'active' | 'inactive';
  created_at: string;
  updated_at: string;
}

export interface GlobalCandidateUser {
  id: number;
  username: string;
  email: string;
}

export interface GlobalOrganizationCreateInput {
  name: string;
  admin_email: string;
}

export interface GlobalOrganizationCreateResult {
  id: string;
  name: string;
  status: 'active' | 'inactive';
  admin_email: string;
  admin_role: string;
  membership_id: string;
  admin_user_id: string;
  admin_account_created: boolean;
  setup_token?: string;
  setup_token_expires_at?: string;
}

export interface GlobalOrganizationUpdateInput {
  name?: string;
  status?: 'active' | 'inactive';
}