/**
 * Unit tests for the dashboard page (frontend-integration slice).
 * Verifies that the summary is data-backed: invoices + policies are read in
 * parallel from the real endpoints, counts are computed over the server
 * responses, the active policy is surfaced, empty/forbidden/error states are
 * explicit and navigation to Vendors/Invoices is present. No invented
 * financial metric is rendered.
 */
import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';

import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/auth/auth.service';
import { Dashboard } from './dashboard';
import { InvoiceSummary } from '../invoices/invoices.models';
import { PolicyVersion } from '../policies/policies.models';

const API = environment.apiBaseUrl;
const ORG = 'org-123';

function invoice(
  id: string,
  status: InvoiceSummary['status'],
  invoice_number = 'INV-100',
): InvoiceSummary {
  return {
    id,
    vendor: { id: 'v1', legal_name: 'Acme Corp', tax_id: 'ACME-1' },
    invoice_number,
    issue_date: '2026-10-01',
    due_date: null,
    amount: '100.00',
    currency: 'USD',
    description: '',
    status,
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
  };
}

function policy(overrides: Partial<PolicyVersion> = {}): PolicyVersion {
  return {
    id: 'p1',
    version: 1,
    is_active: true,
    allowed_currencies: ['USD'],
    max_amount: '1000.00',
    escalation_threshold: '500.00',
    require_due_date: false,
    require_description: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function setUser(auth: AuthService, role: string) {
  auth['user'].set({
    id: 'u',
    username: 'u',
    email: 'u@c.com',
    first_name: '',
    last_name: '',
    memberships: [{ organization_id: ORG, organization_name: 'Ledger Org', role } as never],
  });
}

describe('Dashboard', () => {
  let http: HttpTestingController;
  let auth: AuthService;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  afterEach(() => http.verify());

  it('renders counts and the active policy from real endpoint responses', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();

    const invoicesReq = http.expectOne(`${API}/organizations/${ORG}/invoices/`);
    const policiesReq = http.expectOne(`${API}/organizations/${ORG}/policies/`);
    invoicesReq.flush([
      invoice('i1', 'approved'),
      invoice('i2', 'blocked'),
      invoice('i3', 'pending_approval'),
      invoice('i4', 'received'),
    ]);
    policiesReq.flush([
      policy({ version: 2, is_active: true }),
      policy({ version: 1, is_active: false }),
    ]);
    await fixture.whenStable();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Ledger Org');
    expect(text).toContain('4'); // total invoices stat
    expect(text).toContain('Active policy');
    expect(text).toContain('v2');
    expect(text).toContain('approved');
    expect(text).toContain('blocked');
    expect(text).toContain('pending approval');
    expect(text).toContain('Acme Corp');
    expect(text).toContain('2'); // policy version count
  });

  it('shows the empty state when the organization has no data', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/invoices/`).flush([]);
    http.expectOne(`${API}/organizations/${ORG}/policies/`).flush([]);
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('No invoices yet');
    expect(text).toContain('No active policy');
  });

  it('shows the no-organization state without a membership', async () => {
    auth['user'].set({ id: 'u', username: 'u', email: 'u@c.com', first_name: '', last_name: '' });
    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No active organization');
    http.expectNone(`${API}/organizations/`);
  });

  it('shows the forbidden state on 403', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();
    const invoicesReq = http.expectOne(`${API}/organizations/${ORG}/invoices/`);
    http.expectOne(`${API}/organizations/${ORG}/policies/`);
    invoicesReq.flush({ detail: 'Forbidden' }, { status: 403, statusText: 'Forbidden' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No permission');
  });

  it('shows the error state on server failure with retry', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();
    const invoicesReq = http.expectOne(`${API}/organizations/${ORG}/invoices/`);
    http.expectOne(`${API}/organizations/${ORG}/policies/`);
    invoicesReq.flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Could not load the dashboard');
    expect(fixture.nativeElement.textContent).toContain('Retry');
  });

  it('links to the Vendors and Invoices sections', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/invoices/`).flush([]);
    http.expectOne(`${API}/organizations/${ORG}/policies/`).flush([]);
    await fixture.whenStable();
    fixture.detectChanges();
    const links = Array.from(
      fixture.nativeElement.querySelectorAll('a'),
    ).map((a) => (a as HTMLAnchorElement).getAttribute('href'));
    expect(links).toContain('/app/vendors');
    expect(links).toContain('/app/invoices');
  });

  it('does not render invented financial totals', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(Dashboard);
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/invoices/`).flush([
      invoice('i1', 'approved'),
      invoice('i2', 'blocked'),
    ]);
    http.expectOne(`${API}/organizations/${ORG}/policies/`).flush([]);
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).not.toContain('Total amount');
    expect(text).not.toContain('Amount sum');
  });
});
