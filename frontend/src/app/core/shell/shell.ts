import { Component, signal, computed, inject, type Signal } from '@angular/core';
import type { MembershipSummary, UserProfile } from '../auth/models';
import { CommonModule } from '@angular/common';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../auth/auth.service';
import { CapabilitiesService } from '../auth/capabilities.service';
import { Logo } from '../../shared/logo';

interface NavItem {
  path: string;
  label: string;
  capability?: string; // optional capability required to show the item
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

// Base nav template with capability keys that mirror backend permissions
const NAV_TEMPLATE: NavGroup[] = [
  {
    label: 'Workspace',
    items: [
      { path: '/app', label: 'Dashboard' },
      { path: '/app/invoices', label: 'Invoices' },
      { path: '/app/invoices/upload', label: 'Upload invoice', capability: 'createInvoice' },
      { path: '/app/vendors', label: 'Vendors' },
      { path: '/app/policies', label: 'Policies' },
    ],
  },
  {
    label: 'Administration',
    items: [
      { path: '/app/organizations', label: 'Organizations', capability: 'adminOrg' },
      {
        path: '/app/admin/organizations',
        label: 'Global admin',
        capability: 'adminGlobalOrganizations',
      },
      // Audit is intentionally not a functional API; do not show it.
    ],
  },
];

const CRUMBS: Record<string, string> = {
  '/app': 'Dashboard',
  '/app/invoices': 'Invoices',
  '/app/invoices/upload': 'Upload invoice',
  '/app/vendors': 'Vendors',
  '/app/policies': 'Policies',
  '/app/organizations': 'Organizations',
  '/app/admin/organizations': 'Global admin',
};

const MEMBERS_CRUMB_RE = /^\/app\/organizations\/[^/]+\/members$/;

function crumbFor(url: string): string {
  if (CRUMBS[url]) return CRUMBS[url];
  // Invoice detail and other dynamic app routes get a readable crumb.
  if (/^\/app\/invoices\/upload/.test(url)) return 'Upload invoice';
  if (/^\/app\/invoices\/[^/]+$/.test(url)) return 'Invoice';
  if (MEMBERS_CRUMB_RE.test(url)) return 'Members';
  return 'App';
}

/**
 * Private application shell. Navigation mirrors the backend surface and is
 * grouped by workspace vs administration. The organization picker is an
 * honest placeholder until session data is wired.
 */
@Component({
  selector: 'pb-shell',
  imports: [CommonModule, RouterLink, RouterLinkActive, RouterOutlet, Logo],
  templateUrl: './shell.html',
  styles: `
    .shell {
      display: grid;
      grid-template-columns: 252px 1fr;
      min-height: 100dvh;
    }

    .shell__rail {
      display: flex;
      flex-direction: column;
      border-right: 1px solid var(--pb-line);
      background: var(--pb-surface);
      padding: var(--pb-space-4) var(--pb-space-3);
      position: sticky;
      top: 0;
      height: 100dvh;
    }

    .shell__brand {
      display: block;
      text-decoration: none;
      padding: var(--pb-space-1) var(--pb-space-3) var(--pb-space-4);
    }

    .shell__groups {
      margin-top: var(--pb-space-2);
      display: flex;
      flex-direction: column;
      gap: var(--pb-space-5);
      overflow-y: auto;
    }

    .shell__group-label {
      padding: 0 var(--pb-space-3) var(--pb-space-1);
      font-family: var(--pb-font-mono);
      font-size: 0.625rem;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--pb-muted);
    }

    .shell__group {
      display: flex;
      flex-direction: column;
      gap: 1px;
    }

    .shell__link {
      display: flex;
      align-items: center;
      gap: var(--pb-space-2);
      padding: 0.5rem 0.75rem;
      border-radius: var(--pb-radius-m);
      color: var(--pb-ink-soft);
      text-decoration: none;
      font-size: 0.875rem;
      font-weight: 500;
      transition: background var(--pb-dur) var(--pb-ease),
        color var(--pb-dur) var(--pb-ease);
    }

    .shell__link:hover {
      background: var(--pb-surface-2);
      color: var(--pb-ink);
    }

    .shell__link.is-active {
      background: var(--pb-brand-soft);
      color: var(--pb-brand-text);
      font-weight: 600;
    }

    .shell__link-dot {
      width: 5px;
      height: 5px;
      border-radius: var(--pb-radius-pill);
      background: transparent;
      border: 1px solid var(--pb-line-strong);
    }

    .shell__link.is-active .shell__link-dot {
      background: var(--pb-brand-strong);
      border-color: var(--pb-brand-strong);
    }

    .shell__rail-foot {
      margin-top: auto;
      padding: var(--pb-space-3) var(--pb-space-3) 0;
      border-top: 1px solid var(--pb-line);
      display: grid;
      gap: var(--pb-space-1);
    }

    .shell__rail-note {
      font-family: var(--pb-font-mono);
      font-size: 0.625rem;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--pb-muted);
    }

    .shell__main {
      min-width: 0;
      display: flex;
      flex-direction: column;
    }

    .shell__topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      gap: var(--pb-space-4);
      height: 56px;
      padding-inline: var(--pb-space-5);
      border-bottom: 1px solid var(--pb-line);
      background: color-mix(in srgb, var(--pb-bg) 92%, transparent);
      backdrop-filter: blur(10px);
    }

    .shell__crumb {
      font-family: var(--pb-font-mono);
      font-size: 0.6875rem;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--pb-muted);
    }

    .shell__crumb strong {
      color: var(--pb-ink);
      font-weight: 600;
    }

    .shell__org {
      margin-left: auto;
      display: inline-flex;
      align-items: center;
      gap: var(--pb-space-2);
      padding: 0.3125rem 0.6875rem;
      border: 1px dashed var(--pb-line-strong);
      border-radius: var(--pb-radius-pill);
      font-family: var(--pb-font-mono);
      font-size: 0.6875rem;
      color: var(--pb-muted);
    }

    .shell__org-dot {
      width: 6px;
      height: 6px;
      border-radius: var(--pb-radius-pill);
      background: var(--pb-line-strong);
    }

    .shell__user {
      font-size: var(--pb-text-sm);
      color: var(--pb-ink-soft);
      white-space: nowrap;
    }

    .shell__signout {
      padding: 0.4375rem 0.8125rem;
      border: 1px solid var(--pb-line-strong);
      border-radius: var(--pb-radius-m);
      background: transparent;
      color: var(--pb-ink-soft);
      font-size: var(--pb-text-sm);
      font-weight: 600;
      transition: border-color var(--pb-dur) var(--pb-ease),
        color var(--pb-dur) var(--pb-ease);
    }

    .shell__signout:hover {
      border-color: var(--pb-blocked);
      color: var(--pb-blocked);
    }

    @media (max-width: 860px) {
      .shell__user {
        display: none;
      }
    }

    .shell__burger {
      display: none;
      flex-direction: column;
      gap: 4px;
      background: none;
      border: 0;
      padding: 6px;
    }

    .shell__burger span {
      width: 18px;
      height: 2px;
      background: var(--pb-ink);
      border-radius: 2px;
    }

    .shell__content {
      padding: var(--pb-space-6) var(--pb-space-5) var(--pb-space-9);
      max-width: 1040px;
      width: 100%;
    }

    .shell__overlay {
      position: fixed;
      inset: 0;
      background: rgb(15 20 10 / 0.4);
      z-index: 30;
      opacity: 0;
      pointer-events: none;
      transition: opacity var(--pb-dur) var(--pb-ease);
    }

    @media (max-width: 900px) {
      .shell {
        grid-template-columns: 1fr;
      }

      .shell__rail {
        position: fixed;
        inset: 0 auto 0 0;
        z-index: 40;
        width: 264px;
        transform: translateX(-100%);
        transition: transform var(--pb-dur) var(--pb-ease);
        box-shadow: var(--pb-shadow-pop);
      }

      .shell__rail.is-open {
        transform: none;
      }

      .shell__overlay.is-visible {
        opacity: 1;
        pointer-events: auto;
      }

      .shell__burger {
        display: inline-flex;
      }
    }
  `,
})
export class Shell {
  // Expose a computed nav filtered by capabilities at render time.
  protected readonly railOpen = signal(false);
  protected readonly crumb = signal('');

  protected readonly user!: Signal<UserProfile | null>;
  protected readonly membership!: Signal<MembershipSummary | null>;
  protected readonly cap = inject(CapabilitiesService);

  // Computed nav for template consumption
  protected readonly nav = computed((): NavGroup[] => {
    // Filter NAV_TEMPLATE by capability checks and membership presence
    return NAV_TEMPLATE.map((g) => ({
      label: g.label,
      items: g.items.filter((it) => {
        if (it.capability) return this.cap.has(it.capability);
        return this.cap.hasMembership();
      }),
    })).filter((g) => g.items.length > 0);
  });

  constructor(
    private readonly router: Router,
    private readonly auth: AuthService,
  ) {
    this.user = this.auth.user;
    this.membership = this.auth.currentMembership;
    this.router.events.subscribe(() => {
      this.crumb.set(crumbFor(this.router.url));
    });
  }

  protected async signOut(): Promise<void> {
    await this.auth.logout();
    await this.router.navigate(['/login']);
  }

  protected toggleRail(): void {
    this.railOpen.update((open) => !open);
  }

  protected closeRail(): void {
    this.railOpen.set(false);
  }
}