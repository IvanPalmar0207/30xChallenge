import { computed, Injectable, signal } from '@angular/core';
import { AuthService } from './auth.service';

/**
 * Centralized capability mapping based on the active membership's role.
 * Keeps UI decisions in one place and mirrors backend permissions.
 */
@Injectable({ providedIn: 'root' })
export class CapabilitiesService {
  constructor(private readonly auth: AuthService) {}

  // Convenience accessors
  private readonly membership = computed(() => this.auth.currentMembership());
  readonly hasMembership = computed(() => {
    return !!(this.auth.isAuthed() && this.membership());
  });

  // Role helpers
  private role(): string | null {
    return this.membership() ? (this.membership() as any).role ?? null : null;
  }

  // Capability checks (mirror backend rules in organizations/permissions.py)
  canViewDashboard() {
    return this.hasMembership();
  }

  canViewInvoices() {
    return this.hasMembership();
  }

  canCreateInvoice() {
    const r = this.role();
    return r === 'FINANCE_ADMIN' || r === 'OPERATOR';
  }

  /** Triggers the deterministic policy engine on a received invoice. */
  canEvaluateInvoice() {
    return this.canCreateInvoice();
  }

  canApproveInvoice() {
    const r = this.role();
    return r === 'APPROVER';
  }

  canManageVendors() {
    const r = this.role();
    return r === 'FINANCE_ADMIN';
  }

  canManagePolicies() {
    const r = this.role();
    return r === 'FINANCE_ADMIN';
  }

  canAdminOrganization() {
    const r = this.role();
    return r === 'FINANCE_ADMIN';
  }

  /** Global platform administration (Django superuser) — UI visibility only. */
  canAdminGlobalOrganizations() {
    // The backend is the authority: every /admin/ endpoint re-checks
    // is_superuser server-side. This flag only decides whether to render
    // the nav entry and is never treated as a security mechanism.
    return !!(this.auth.isAuthed() && this.auth.user()?.is_global_admin);
  }

  // Audit is not a functional API yet; hide it.
  canViewAudit() {
    return false;
  }

  // Generic helper usable from templates
  has(capability: string): boolean {
    switch (capability) {
      case 'createInvoice':
        return this.canCreateInvoice();
      case 'evaluateInvoice':
        return this.canEvaluateInvoice();
      case 'approveInvoice':
        return this.canApproveInvoice();
      case 'manageVendors':
        return this.canManageVendors();
      case 'managePolicies':
        return this.canManagePolicies();
      case 'adminOrg':
        return this.canAdminOrganization();
      case 'adminGlobalOrganizations':
        return this.canAdminGlobalOrganizations();
      case 'viewAudit':
        return this.canViewAudit();
      case 'viewInvoices':
        return this.canViewInvoices();
      default:
        return this.hasMembership();
    }
  }
}
