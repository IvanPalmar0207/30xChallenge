import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';

import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/auth/auth.service';
import {
  OrganizationsPage,
} from './organizations';
import { OrganizationsService } from './organizations.service';

const API = environment.apiBaseUrl;

describe('OrganizationsService', () => {
  let service: OrganizationsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(OrganizationsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists organizations from the real endpoint', async () => {
    const promise = new Promise<number>((resolve, reject) =>
      service.list().subscribe({ next: (v) => resolve(v.length), error: reject }),
    );
    const req = http.expectOne(`${API}/organizations/`);
    expect(req.request.method).toBe('GET');
    req.flush([
      { id: 'o1', name: 'Ledger Org', status: 'active', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
    ]);
    expect(await promise).toBe(1);
  });
});

describe('OrganizationsPage', () => {
  let http: HttpTestingController;
  let auth: AuthService;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      imports: [OrganizationsPage],
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

  it('renders data with the active badge after loading', async () => {
    auth['user'].set({
      id: 'u', username: 'u', email: 'u@c.com', first_name: '', last_name: '',
      memberships: [{ organization_id: 'o1', organization_name: 'Ledger Org', role: 'OPERATOR' }],
    });
    const fixture = TestBed.createComponent(OrganizationsPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/`);
    req.flush([
      { id: 'o1', name: 'Ledger Org', status: 'active', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
      { id: 'o2', name: 'Other Org', status: 'active', created_at: '2026-01-02T00:00:00Z', updated_at: '2026-01-02T00:00:00Z' },
    ]);
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Ledger Org');
    expect(text).toContain('Other Org');
    expect(text).toContain('OPERATOR'); // role rendered from /me memberships
    expect(text).toContain('active'); // status badge
    const rows = fixture.nativeElement.querySelectorAll('tbody tr') as NodeListOf<HTMLElement>;
    expect(rows.length).toBe(2);
  });

  it('shows the Members link only to a FINANCE_ADMIN of that organization', async () => {
    auth['user'].set({
      id: 'u', username: 'u', email: 'u@c.com', first_name: '', last_name: '',
      memberships: [
        { organization_id: 'o1', organization_name: 'Ledger Org', role: 'FINANCE_ADMIN' },
        { organization_id: 'o2', organization_name: 'Other Org', role: 'OPERATOR' },
      ],
    });
    const fixture = TestBed.createComponent(OrganizationsPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/`);
    req.flush([
      { id: 'o1', name: 'Ledger Org', status: 'active', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
      { id: 'o2', name: 'Other Org', status: 'active', created_at: '2026-01-02T00:00:00Z', updated_at: '2026-01-02T00:00:00Z' },
    ]);
    await fixture.whenStable();
    fixture.detectChanges();
    const html = (fixture.nativeElement as HTMLElement).innerHTML;
    // ONLY the FINANCE_ADMIN row shows the Members action.
    const links = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('a'),
    ).filter((a) => a.textContent?.includes('Members'));
    expect(links.length).toBe(1);
    expect(html).toContain('Ledger Org');
    expect(links[0].getAttribute('href')).toBe('/app/organizations/o1/members');
  });

  it('hides the Members link from ordinary roles', async () => {
    auth['user'].set({
      id: 'u', username: 'u', email: 'u@c.com', first_name: '', last_name: '',
      memberships: [
        { organization_id: 'o1', organization_name: 'Ledger Org', role: 'OPERATOR' },
        { organization_id: 'o2', organization_name: 'Other Org', role: 'APPROVER' },
      ],
    });
    const fixture = TestBed.createComponent(OrganizationsPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/`);
    req.flush([
      { id: 'o1', name: 'Ledger Org', status: 'active', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
      { id: 'o2', name: 'Other Org', status: 'active', created_at: '2026-01-02T00:00:00Z', updated_at: '2026-01-02T00:00:00Z' },
    ]);
    await fixture.whenStable();
    fixture.detectChanges();
    const links = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('a'),
    ).filter((a) => a.textContent?.includes('Members'));
    expect(links.length).toBe(0);
  });

  it('shows the forbidden state on 403', async () => {
    const fixture = TestBed.createComponent(OrganizationsPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/`);
    req.flush({ detail: 'Forbidden' }, { status: 403, statusText: 'Forbidden' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No permission');
  });

  it('shows the error state on server failure with retry', async () => {
    const fixture = TestBed.createComponent(OrganizationsPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/`);
    req.flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Could not load');
    expect(fixture.nativeElement.textContent).toContain('Retry');
  });

  it('shows the empty state when the list is empty', async () => {
    const fixture = TestBed.createComponent(OrganizationsPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/`);
    req.flush([]);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No organizations yet');
  });
});