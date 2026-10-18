import { TestBed } from '@angular/core/testing';
import { HttpClient, HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { HttpTestingController } from '@angular/common/http/testing';

import { OrganizationsAdminPage } from './organizations-admin';
import { environment } from '../../../environments/environment';

const API = environment.apiBaseUrl;

describe('OrganizationsAdminPage', () => {
  let http: HttpTestingController;
  let fixture: import('@angular/core/testing').ComponentFixture<OrganizationsAdminPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OrganizationsAdminPage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(OrganizationsAdminPage);
  });

  afterEach(() => http.verify());

  function flushOrganizations(): void {
    fixture.detectChanges();
    http
      .expectOne(`${API}/admin/organizations/`)
      .flush([
        { id: 'o1', name: 'Acme', status: 'active', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
        { id: 'o2', name: 'Globex', status: 'inactive', created_at: '2026-01-02T00:00:00Z', updated_at: '2026-01-02T00:00:00Z' },
      ]);
    fixture.detectChanges();
  }

  it('loads and renders the organization list with statuses', () => {
    flushOrganizations();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Global administration');
    expect(text).toContain('Acme');
    expect(text).toContain('Globex');
    expect(text).toContain('active');
    expect(text).toContain('inactive');
  });

  it('shows a clear forbidden state on 404/403', () => {
    fixture.detectChanges();
    http.expectOne(`${API}/admin/organizations/`).flush({}, { status: 404, statusText: 'Not found' });
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('No permission');
  });

  it('submits the create form with name and normalized admin email', () => {
    flushOrganizations();

    const [name, email] = (fixture.nativeElement as HTMLElement).querySelectorAll('input');
    name.value = '  New Org  ';
    name.dispatchEvent(new Event('input'));
    email.value = ' Boss@Example.com ';
    email.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    // The email input triggers the candidate-user autocomplete lookup.
    http.expectOne(`${API}/admin/users/?q=Boss%40Example.com`).flush([]);

    Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('button'),
    ).find((b) => b.textContent?.includes('Create organization'))!
      .click();

    const req = http.expectOne(`${API}/admin/organizations/`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ name: 'New Org', admin_email: 'boss@example.com' });
    req.flush(
      {
        id: 'o3',
        name: 'New Org',
        status: 'active',
        admin_email: 'boss@example.com',
        admin_role: 'FINANCE_ADMIN',
        membership_id: 'm3',
        admin_user_id: 'u3',
        admin_account_created: true,
        setup_token: 'TOK',
      },
      { status: 201, statusText: 'Created' },
    );
    fixture.detectChanges();

    // submit() reloads the list after a successful creation.
    http.expectOne(`${API}/admin/organizations/`).flush([]);
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('New Org');
    expect(text).toContain('FINANCE_ADMIN');
    expect(text).toContain('One-time setup token');
  });

  it('rejects a submit missing the admin email', () => {
    flushOrganizations();
    const fixtureEl = fixture.nativeElement as HTMLElement;
    const [name] = fixtureEl.querySelectorAll('input');
    name.value = 'Empty Org';
    name.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const createButton = [...fixtureEl.querySelectorAll('button')].find(
      (b) => b.textContent?.includes('Create organization'),
    )!;
    expect(createButton.disabled).toBe(true);
  });
});