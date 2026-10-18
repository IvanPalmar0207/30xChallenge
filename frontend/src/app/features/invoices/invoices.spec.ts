import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';

import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/auth/auth.service';
import { InvoicesPage } from './invoices';
import { InvoicesService } from './invoices.service';

const API = environment.apiBaseUrl;
const ORG = 'o1';
const INVOICE = {
  id: 'inv1',
  vendor: { id: 'v1', legal_name: 'Acme Corp', tax_id: 'ACME-1' },
  invoice_number: 'INV-100',
  issue_date: '2026-10-01',
  due_date: null,
  amount: '100.00',
  currency: 'USD',
  description: '',
  status: 'received',
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
};

function member(orgId: string, role: string) {
  return (service: AuthService) =>
    service['user'].set({
      id: 'u', username: 'u', email: 'u@c.com', first_name: '', last_name: '',
      memberships: [{ organization_id: orgId, organization_name: 'Ledger Org', role } as never],
    });
}

describe('InvoicesService', () => {
  let service: InvoicesService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(InvoicesService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists invoices for the given organization', async () => {
    const p = service.list(ORG).toPromise();
    const req = http.expectOne(`${API}/organizations/${ORG}/invoices/`);
    expect(req.request.method).toBe('GET');
    req.flush([INVOICE]);
    expect((await p)?.length).toBe(1);
  });
});

describe('InvoicesPage', () => {
  let http: HttpTestingController;
  let auth: AuthService;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      imports: [InvoicesPage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  afterEach(() => http.verify());

  it('renders real invoice rows with status badge', async () => {
    member(ORG, 'OPERATOR')(auth);
    const fixture = TestBed.createComponent(InvoicesPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/invoices/`);
    req.flush([INVOICE]);
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('INV-100');
    expect(text).toContain('Acme Corp');
    expect(text).toContain('received');
    const rows = fixture.nativeElement.querySelectorAll('tbody tr');
    expect(rows.length).toBe(1);
  });

  it('shows forbidden on 403', async () => {
    member(ORG, 'OPERATOR')(auth);
    const fixture = TestBed.createComponent(InvoicesPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/invoices/`);
    req.flush({ detail: 'Forbidden' }, { status: 403, statusText: 'Forbidden' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No permission');
  });

  it('shows error with retry on server failure', async () => {
    member(ORG, 'OPERATOR')(auth);
    const fixture = TestBed.createComponent(InvoicesPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/invoices/`);
    req.flush({ detail: 'x' }, { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Could not load invoices');
    expect(fixture.nativeElement.textContent).toContain('Retry');
  });

  it('shows empty when the organization has no invoices', async () => {
    member(ORG, 'OPERATOR')(auth);
    const fixture = TestBed.createComponent(InvoicesPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/invoices/`);
    req.flush([]);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No invoices yet');
  });

  it('shows no-organization state without a membership', async () => {
    auth['user'].set({ id: 'u', username: 'u', email: 'u@c.com', first_name: '', last_name: '' });
    const fixture = TestBed.createComponent(InvoicesPage);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No active organization');
    http.expectNone(`${API}/organizations/`);
  });
});