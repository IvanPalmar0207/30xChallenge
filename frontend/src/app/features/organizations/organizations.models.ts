/** Real contract of GET /api/v1/organizations/ (OrganizationSerializer). */
export interface OrganizationSummary {
  id: string;
  name: string;
  status: 'active' | 'inactive';
  created_at: string;
  updated_at: string;
}