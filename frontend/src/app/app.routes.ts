import { Routes } from '@angular/router';

import { Landing } from './public/landing/landing';
import { Shell } from './core/shell/shell';
import { LoginPage } from './features/auth/login';
import { authGuard } from './core/auth/auth.guard';

/**
 * Public experiences are standalone; the private application lives under
 * `/app` inside the shell, guarded by auth (frontend-only gate — Django
 * remains the authority).
 */
export const routes: Routes = [
  { path: '', component: Landing },
  { path: 'login', component: LoginPage },
  {
    path: 'setup-account',
    loadComponent: () =>
      import('./features/auth/setup').then((m) => m.SetupAccountPage),
  },
  {
    path: 'app',
    component: Shell,
    canActivate: [authGuard],
    children: [
      {
        path: '',
        pathMatch: 'full',
        loadComponent: () =>
          import('./features/dashboard/dashboard').then((m) => m.Dashboard),
      },
      {
        path: 'organizations',
        loadComponent: () =>
          import('./features/organizations/organizations').then(
            (m) => m.OrganizationsPage,
          ),
      },
      {
        path: 'organizations/:id/members',
        loadComponent: () =>
          import('./features/organizations/organizations-members').then(
            (m) => m.OrganizationsMembersPage,
          ),
      },
      {
        path: 'vendors',
        loadComponent: () =>
          import('./features/vendors/vendors').then((m) => m.VendorsPage),
      },
      {
        path: 'invoices',
        loadComponent: () =>
          import('./features/invoices/invoices').then((m) => m.InvoicesPage),
      },
      {
        path: 'invoices/upload',
        loadComponent: () =>
          import('./features/extraction/extraction').then((m) => m.ExtractionPage),
      },
      {
        path: 'invoices/:id',
        loadComponent: () =>
          import('./features/invoices/invoice-detail').then(
            (m) => m.InvoiceDetailPage,
          ),
      },
      {
        path: 'policies',
        loadComponent: () =>
          import('./features/policies/policies').then((m) => m.PoliciesPage),
      },
      {
        path: 'admin/organizations',
        loadComponent: () =>
          import('./features/organizations-admin/organizations-admin').then(
            (m) => m.OrganizationsAdminPage,
          ),
      },
      {
        path: 'audit',
        loadComponent: () =>
          import('./features/audit/audit').then((m) => m.AuditPage),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];