/**
 * Unit tests for the policies page (Slice 6 contract).
 * Verifies version list rendering, role gating, the create payload (parsed
 * currencies, amount null semantics) and the client-side coherence check
 * that mirrors the backend rule (escalation_threshold <= max_amount).
 */
import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';

import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/auth/auth.service';
import { PoliciesPage } from './policies';
import { PolicyVersion } from './policies.models';

const API = environment.apiBaseUrl;
const ORG = 'org-123';

function policy(
  overrides: Partial<PolicyVersion> = {},
): PolicyVersion {
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

describe('PoliciesPage', () => {
  let http: HttpTestingController;
  let auth: AuthService;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      imports: [PoliciesPage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  afterEach(() => http.verify());

  it('renders policy versions with active and superseded badges', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(PoliciesPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/policies/`);
    req.flush([
      policy({ id: 'p1', version: 2, is_active: true, created_at: '2026-02-01T00:00:00Z' }),
      policy({
        id: 'p0',
        version: 1,
        is_active: false,
        max_amount: null,
        escalation_threshold: null,
      }),
    ]);
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Active policy · v2');
    expect(text).toContain('active');
    expect(text).toContain('superseded');
    expect(text).toContain('no cap');
  });

  it('shows the empty state when no policy is configured', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(PoliciesPage);
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/policies/`).flush([]);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No policies configured');
  });

  it('shows the forbidden state on 403', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(PoliciesPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/policies/`);
    req.flush({ detail: 'Forbidden' }, { status: 403, statusText: 'Forbidden' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No permission');
  });

  it('shows the error state on server failure with retry', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(PoliciesPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/policies/`);
    req.flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Could not load policies');
    expect(fixture.nativeElement.textContent).toContain('Retry');
  });

  it('hides the create form from read-only roles', async () => {
    setUser(auth, 'OPERATOR');
    const fixture = TestBed.createComponent(PoliciesPage);
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/policies/`).flush([]);
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).not.toContain('New policy version');
  });

  it('FINANCE_ADMIN creates a policy with parsed currencies and amounts', async () => {
    setUser(auth, 'FINANCE_ADMIN');
    const fixture = TestBed.createComponent(PoliciesPage);
    const component = fixture.componentInstance;
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/policies/`).flush([]);
    await fixture.whenStable();
    fixture.detectChanges();

    component['openCreate']();
    component['currencies'].set(' usd , EUR, usd ');
    component['maxAmount'].set('1000.00');
    component['escalationThreshold'].set('500.00');
    component['requireDueDate'].set(true);
    expect(component['canSubmit']()).toBe(true);
    component['submit']();

    const create = http.expectOne(`${API}/organizations/${ORG}/policies/`);
    expect(create.request.method).toBe('POST');
    expect(create.request.body).toEqual({
      allowed_currencies: ['USD', 'EUR'],
      max_amount: '1000.00',
      escalation_threshold: '500.00',
      require_due_date: true,
      require_description: false,
    });
    create.flush(policy({ id: 'p2', version: 1, is_active: true }));

    // The page reloads the list after a successful mutation.
    http.expectOne(`${API}/organizations/${ORG}/policies/`).flush([
      policy({ id: 'p2', version: 1, is_active: true }),
    ]);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Policy v1 created');
  });

  it('sends empty amount fields as null and empty currencies as []', async () => {
    setUser(auth, 'FINANCE_ADMIN');
    const fixture = TestBed.createComponent(PoliciesPage);
    const component = fixture.componentInstance;
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/policies/`).flush([]);
    await fixture.whenStable();
    fixture.detectChanges();

    component['openCreate']();
    component['currencies'].set('');
    component['submit']();

    const create = http.expectOne(`${API}/organizations/${ORG}/policies/`);
    expect(create.request.body).toEqual({
      allowed_currencies: [],
      max_amount: null,
      escalation_threshold: null,
      require_due_date: false,
      require_description: false,
    });
    create.flush(policy());
    http.expectOne(`${API}/organizations/${ORG}/policies/`).flush([]);
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('blocks a policy whose escalation_threshold exceeds max_amount client-side', async () => {
    setUser(auth, 'FINANCE_ADMIN');
    const fixture = TestBed.createComponent(PoliciesPage);
    const component = fixture.componentInstance;
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/policies/`).flush([]);
    await fixture.whenStable();
    fixture.detectChanges();

    component['openCreate']();
    component['maxAmount'].set('100.00');
    component['escalationThreshold'].set('200.00');
    component['submit']();

    http.expectNone(`${API}/organizations/${ORG}/policies/`);
    expect(component['formError']()).toContain('must not exceed max_amount');
  });
});
