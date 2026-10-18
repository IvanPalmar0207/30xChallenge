/**
 * Unit tests for the vendors page (Slice 3 contract).
 * Verifies list rendering, role gating, create/edit payloads and the explicit
 * activate/deactivate operations against the real API URLs used by the page.
 */
import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { signal } from '@angular/core';

import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/auth/auth.service';
import { VendorsPage } from './vendors';
import { VendorSummary } from './vendors.models';

const API = environment.apiBaseUrl;
const ORG = 'org-123';

function vendor(
  id: string,
  legal_name: string,
  tax_id: string,
  status: VendorSummary['status'] = 'active',
): VendorSummary {
  return {
    id,
    organization: { id: ORG, name: 'Ledger Org', status: 'active' },
    legal_name,
    tax_id,
    status,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
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

describe('VendorsPage', () => {
  let http: HttpTestingController;
  let auth: AuthService;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      imports: [VendorsPage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  afterEach(() => http.verify());

  it('renders vendors with their normalized tax ids and status badges', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(VendorsPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/vendors/`);
    expect(req.request.method).toBe('GET');
    req.flush([
      vendor('v1', 'Acme Corp', 'ACME-1', 'active'),
      vendor('v2', 'Beta Ltd', 'BETA-2', 'inactive'),
    ]);
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Acme Corp');
    expect(text).toContain('ACME-1');
    expect(text).toContain('Beta Ltd');
    expect(text).toContain('BETA-2');
    expect(text).toContain('active');
    expect(text).toContain('inactive');
  });

  it('shows the empty state when the list is empty', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(VendorsPage);
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/vendors/`).flush([]);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No vendors yet');
  });

  it('shows the forbidden state on 403', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(VendorsPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/vendors/`);
    req.flush({ detail: 'Forbidden' }, { status: 403, statusText: 'Forbidden' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No permission');
  });

  it('shows the error state on server failure with retry', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(VendorsPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/vendors/`);
    req.flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Could not load vendors');
    expect(fixture.nativeElement.textContent).toContain('Retry');
  });

  it('hides mutation controls from read-only roles', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(VendorsPage);
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/vendors/`).flush([
      vendor('v1', 'Acme Corp', 'ACME-1'),
    ]);
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).not.toContain('New vendor');
    expect(text).not.toContain('Edit');
    expect(text).not.toContain('Deactivate');
  });

  it('FINANCE_ADMIN creates a vendor with normalized tax id and reloads', async () => {
    setUser(auth, 'FINANCE_ADMIN');
    const fixture = TestBed.createComponent(VendorsPage);
    const component = fixture.componentInstance;
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/vendors/`).flush([]);
    await fixture.whenStable();
    fixture.detectChanges();

    component['openCreate']();
    component['legalName'].set('Gamma GmbH');
    component['taxId'].set(' gamma-3 ');
    fixture.detectChanges();
    expect(component['canSubmit']()).toBe(true);
    component['submit']();

    const create = http.expectOne(`${API}/organizations/${ORG}/vendors/`);
    expect(create.request.method).toBe('POST');
    expect(create.request.body).toEqual({ legal_name: 'Gamma GmbH', tax_id: 'GAMMA-3' });
    create.flush(vendor('v3', 'Gamma GmbH', 'GAMMA-3'));

    // The page reloads the list after a successful mutation.
    const reload = http.expectOne(`${API}/organizations/${ORG}/vendors/`);
    expect(reload.request.method).toBe('GET');
    reload.flush([vendor('v3', 'Gamma GmbH', 'GAMMA-3')]);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Gamma GmbH');
  });

  it('FINANCE_ADMIN sees edit payloads as PATCH with normalized tax id', async () => {
    setUser(auth, 'FINANCE_ADMIN');
    const fixture = TestBed.createComponent(VendorsPage);
    const component = fixture.componentInstance;
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/vendors/`).flush([
      vendor('v1', 'Acme Corp', 'ACME-1'),
    ]);
    await fixture.whenStable();
    fixture.detectChanges();

    component['openEdit'](component['vendors']()[0]);
    component['legalName'].set('Acme Corporation');
    component['submit']();

    const patch = http.expectOne(`${API}/organizations/${ORG}/vendors/v1/`);
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.body).toEqual({
      legal_name: 'Acme Corporation',
      tax_id: 'ACME-1',
    });
    patch.flush(vendor('v1', 'Acme Corporation', 'ACME-1'));
    http.expectOne(`${API}/organizations/${ORG}/vendors/`).flush([
      vendor('v1', 'Acme Corporation', 'ACME-1'),
    ]);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Acme Corporation');
  });

  it('deactivate posts to the deactivate endpoint and reloads', async () => {
    setUser(auth, 'FINANCE_ADMIN');
    const fixture = TestBed.createComponent(VendorsPage);
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/vendors/`).flush([
      vendor('v1', 'Acme Corp', 'ACME-1', 'active'),
    ]);
    await fixture.whenStable();
    fixture.detectChanges();

    const button = Array.from(
      fixture.nativeElement.querySelectorAll('button'),
    ).find((b) => (b as HTMLButtonElement).textContent?.includes('Deactivate')) as
      | HTMLButtonElement
      | undefined;
    expect(button).toBeDefined();
    button!.click();

    const deactivate = http.expectOne(`${API}/organizations/${ORG}/vendors/v1/deactivate/`);
    expect(deactivate.request.method).toBe('POST');
    deactivate.flush(vendor('v1', 'Acme Corp', 'ACME-1', 'inactive'));
    http.expectOne(`${API}/organizations/${ORG}/vendors/`).flush([
      vendor('v1', 'Acme Corp', 'ACME-1', 'inactive'),
    ]);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('inactive');
  });

  it('activate posts to the activate endpoint and reloads', async () => {
    setUser(auth, 'FINANCE_ADMIN');
    const fixture = TestBed.createComponent(VendorsPage);
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/vendors/`).flush([
      vendor('v2', 'Beta Ltd', 'BETA-2', 'inactive'),
    ]);
    await fixture.whenStable();
    fixture.detectChanges();

    const button = Array.from(
      fixture.nativeElement.querySelectorAll('button'),
    ).find((b) => (b as HTMLButtonElement).textContent?.includes('Activate')) as
      | HTMLButtonElement
      | undefined;
    expect(button).toBeDefined();
    button!.click();

    const activate = http.expectOne(`${API}/organizations/${ORG}/vendors/v2/activate/`);
    expect(activate.request.method).toBe('POST');
    activate.flush(vendor('v2', 'Beta Ltd', 'BETA-2', 'active'));
    http.expectOne(`${API}/organizations/${ORG}/vendors/`).flush([
      vendor('v2', 'Beta Ltd', 'BETA-2', 'active'),
    ]);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('active');
  });
});
