import { ComponentFixture } from '@angular/core/testing';
import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import {
  ActivatedRoute,
  convertToParamMap,
  provideRouter,
} from '@angular/router';

import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/auth/auth.service';
import { InvoiceDetailPage } from './invoice-detail';
import { InvoicesService } from './invoices.service';

const API = environment.apiBaseUrl;
const ORG = 'o1';
const ID = 'inv1';
const INVOICE = {
  id: ID,
  vendor: { id: 'v1', legal_name: 'Acme Corp', tax_id: 'ACME-1' },
  invoice_number: 'INV-100',
  issue_date: '2026-10-01',
  due_date: '2026-11-01',
  amount: '100.00',
  currency: 'USD',
  description: 'Consulting',
  status: 'received',
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
};
const EVALUATE_URL = `${API}/organizations/${ORG}/invoices/${ID}/evaluate/`;
const DECISION_URL = `${API}/organizations/${ORG}/invoices/${ID}/decision/`;

function authWithMembership(role: string) {
  const auth = TestBed.inject(AuthService);
  auth['user'].set({
    id: 'u', username: 'u', email: 'u@c.com', first_name: '', last_name: '',
    memberships: [{ organization_id: ORG, organization_name: 'Ledger Org', role }] as never,
  });
}

/** Only the visible action buttons (button element text, trimmed). */
function actionLabels(fixture: ComponentFixture<InvoiceDetailPage>): string[] {
  const buttons = fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>;
  return Array.from(buttons)
    .map((b) => (b.textContent ?? '').replace(/\s+/g, ' ').trim())
    .filter(Boolean);
}

describe('InvoicesService.get', () => {
  let service: InvoicesService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(InvoicesService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('fetches one invoice by id for the organization', async () => {
    const promise = service.get(ORG, ID).toPromise();
    const req = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
    expect(req.request.method).toBe('GET');
    req.flush(INVOICE);
    expect((await promise)?.invoice_number).toBe('INV-100');
  });

  it('posts evaluate to the engine endpoint', async () => {
    const promise = service.evaluate(ORG, ID).toPromise();
    const req = http.expectOne(EVALUATE_URL);
    expect(req.request.method).toBe('POST');
    req.flush({
      invoice_id: ID,
      result: 'blocked',
      reason_code: 'amount_exceeds_max',
      reason_detail: 'Amount 5000.00 exceeds the policy maximum 1000.00.',
      policy_version: 1,
    });
    const result = await promise;
    expect(result?.result).toBe('blocked');
    expect(result?.reason_code).toBe('amount_exceeds_max');
  });

  it('reads the recorded decision for the invoice', async () => {
    const promise = service.decision(ORG, ID).toPromise();
    const req = http.expectOne(DECISION_URL);
    expect(req.request.method).toBe('GET');
    req.flush({
      result: 'escalated',
      reason_code: 'no_active_policy',
      reason_detail: 'No active policy is configured for this organization.',
      policy_version: null,
    });
    const decision = await promise;
    expect(decision?.reason_code).toBe('no_active_policy');
  });
});

describe('InvoiceDetailPage', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      imports: [InvoiceDetailPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ id: ID }) } },
        },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('renders real invoice detail fields', async () => {
    authWithMembership('OPERATOR');
    const fixture = TestBed.createComponent(InvoiceDetailPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
    req.flush({ ...INVOICE, status: 'approved' });
    const decision = http.expectOne(DECISION_URL);
    decision.flush({
      result: 'approved',
      reason_code: 'policy_ok',
      reason_detail: 'The invoice complies with the active policy.',
      policy_version: 1,
    });
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('INV-100');
    expect(text).toContain('Acme Corp');
    expect(text).toContain('ACME-1');
    expect(text).toContain('approved');
    expect(text).toContain('100.00');
    expect(text).toContain('← Invoices');
  });

  it('shows forbidden on 403', async () => {
    authWithMembership('OPERATOR');
    const fixture = TestBed.createComponent(InvoiceDetailPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
    req.flush({ detail: 'Forbidden' }, { status: 403, statusText: 'Forbidden' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No permission');
  });

  it('shows not-found on 404', async () => {
    authWithMembership('OPERATOR');
    const fixture = TestBed.createComponent(InvoiceDetailPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
    req.flush({ detail: 'Not found' }, { status: 404, statusText: 'Not Found' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Invoice not found');
  });

  it('shows error on server failure', async () => {
    authWithMembership('OPERATOR');
    const fixture = TestBed.createComponent(InvoiceDetailPage);
    fixture.detectChanges();
    const req = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
    req.flush({ detail: 'x' }, { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Could not load the invoice');
  });
});

describe('InvoiceDetailPage — received invoice evaluation', () => {
  let http: HttpTestingController;

  function setup(role: string) {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      imports: [InvoiceDetailPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id: ID }) } } },
      ],
    });
    authWithMembership(role);
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(InvoiceDetailPage);
    fixture.detectChanges();
    return fixture;
  }

  afterEach(() => http.verify());

  it('shows the Evaluate action only to OPERATOR/FINANCE_ADMIN on a received invoice', async () => {
    for (const role of ['OPERATOR', 'FINANCE_ADMIN']) {
      const fixture = setup(role);
      const req = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
      req.flush({ ...INVOICE, status: 'received' });
      await fixture.whenStable();
      fixture.detectChanges();
      const text = fixture.nativeElement.textContent as string;
      expect(text).toContain('Evaluate invoice');
      // Only the evaluate button renders; no human approval actions.
      expect(actionLabels(fixture)).toEqual(['Evaluate invoice']);
      fixture.destroy();
    }
  });

  it('hides the Evaluate action from APPROVER and AUDITOR on a received invoice', async () => {
    for (const role of ['APPROVER', 'AUDITOR']) {
      const fixture = setup(role);
      const req = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
      req.flush({ ...INVOICE, status: 'received' });
      await fixture.whenStable();
      fixture.detectChanges();
      expect(actionLabels(fixture)).toEqual([]);
      fixture.destroy();
    }
  });

  it('evaluates a received invoice and presents the real engine result', async () => {
    const fixture = setup('OPERATOR');
    http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`).flush({ ...INVOICE, status: 'received' });
    await fixture.whenStable();
    fixture.detectChanges();

    const button = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((b) => b.textContent?.includes('Evaluate invoice'));
    expect(button).toBeTruthy();
    button!.click();
    await new Promise((r) => setTimeout(r, 0));

    const post = http.expectOne(EVALUATE_URL);
    expect(post.request.method).toBe('POST');
    post.flush({
      invoice_id: ID,
      result: 'blocked',
      reason_code: 'amount_exceeds_max',
      reason_detail: 'Amount 5000.00 exceeds the policy maximum 1000.00.',
      policy_version: 1,
    });
    await new Promise((r) => setTimeout(r, 0));

    // The component refreshes the invoice; the backend now reports `blocked`.
    const refresh = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
    refresh.flush({ ...INVOICE, status: 'blocked' });
    // Evaluated states also load the recorded engine decision.
    const decision = http.expectOne(DECISION_URL);
    decision.flush({
      result: 'blocked',
      reason_code: 'amount_exceeds_max',
      reason_detail: 'Amount 5000.00 exceeds the policy maximum 1000.00.',
      policy_version: 1,
    });
    await fixture.whenStable();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('blocked');
    // The real engine reason from the evaluate response is presented.
    expect(text).toContain('Amount 5000.00 exceeds the policy maximum 1000.00.');
    // No transitions remain available on the terminal `blocked` state.
    expect(actionLabels(fixture)).toEqual([]);
  });

  it('shows a recoverable error when the server fails without simulating success', async () => {
    const fixture = setup('OPERATOR');
    http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`).flush({ ...INVOICE, status: 'received' });
    await fixture.whenStable();
    fixture.detectChanges();

    const button = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((b) => b.textContent?.includes('Evaluate invoice'));
    button!.click();
    await new Promise((r) => setTimeout(r, 0));

    const post = http.expectOne(EVALUATE_URL);
    post.flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('The evaluation could not be completed. Try again.');
    // The invoice is still received and the retry action remains available.
    expect(actionLabels(fixture)).toEqual(['Evaluate invoice']);
    expect(text).toContain('received');
  });

  it('does not fire concurrent evaluate requests on repeated clicks', async () => {
    const fixture = setup('OPERATOR');
    http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`).flush({ ...INVOICE, status: 'received' });
    await fixture.whenStable();
    fixture.detectChanges();

    const button = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((b) => b.textContent?.includes('Evaluate invoice'));
    // First click starts the request; the button becomes disabled immediately.
    button!.click();
    await new Promise((r) => setTimeout(r, 0));
    // A second click while acting must not create another request.
    button!.click();
    await new Promise((r) => setTimeout(r, 0));

    const posts = http.match((request) => request.url === EVALUATE_URL);
    expect(posts.length).toBe(1);
    posts[0].flush({
      invoice_id: ID,
      result: 'escalated',
      reason_code: 'no_active_policy',
      reason_detail: 'No active policy is configured for this organization.',
      policy_version: null,
    });
    await new Promise((r) => setTimeout(r, 0));
    const refresh = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
    refresh.flush({ ...INVOICE, status: 'pending_approval' });
    const decision = http.expectOne(DECISION_URL);
    decision.flush({
      result: 'escalated',
      reason_code: 'no_active_policy',
      reason_detail: 'No active policy is configured for this organization.',
      policy_version: null,
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('pending_approval');
  });

  it('handles a 409 already-evaluated race by refreshing the real state', async () => {
    const fixture = setup('OPERATOR');
    http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`).flush({ ...INVOICE, status: 'received' });
    await fixture.whenStable();
    fixture.detectChanges();

    const button = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((b) => b.textContent?.includes('Evaluate invoice'));
    button!.click();
    await new Promise((r) => setTimeout(r, 0));

    const post = http.expectOne(EVALUATE_URL);
    post.flush(
      { detail: 'This invoice has already been evaluated.' },
      { status: 409, statusText: 'Conflict' },
    );
    await new Promise((r) => setTimeout(r, 0));
    const refresh = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
    refresh.flush({ ...INVOICE, status: 'blocked' });
    const decision = http.expectOne(DECISION_URL);
    decision.flush({
      result: 'blocked',
      reason_code: 'amount_exceeds_max',
      reason_detail: 'Amount 5000.00 exceeds the policy maximum 1000.00.',
      policy_version: 1,
    });
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    // The persistent feedback keeps explaining the race even after refresh.
    expect(text).toContain('This invoice was already evaluated. Reloading…');
    expect(text).toContain('blocked');
  });
});

describe('InvoiceDetailPage approval actions', () => {
  let http: HttpTestingController;

  function setup(role: string) {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      imports: [InvoiceDetailPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id: ID }) } } },
      ],
    });
    const auth = TestBed.inject(AuthService);
    auth['user'].set({
      id: 'u', username: 'u', email: 'u@c.com', first_name: '', last_name: '',
      memberships: [{ organization_id: ORG, organization_name: 'Ledger Org', role }] as never,
    });
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(InvoiceDetailPage);
    fixture.detectChanges();
    return fixture;
  }

  afterEach(() => http.verify());

  it('shows and performs approve for an APPROVER on a pending invoice', async () => {
    const fixture = setup('APPROVER');
    const req = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
    req.flush({ ...INVOICE, status: 'pending_approval' });
    const decision = http.expectOne(DECISION_URL);
    decision.flush({
      result: 'escalated',
      reason_code: 'amount_exceeds_escalation_threshold',
      reason_detail: 'Amount exceeds the escalation threshold.',
      policy_version: 1,
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(actionLabels(fixture)).toEqual(['Approve', 'Reject']);

    const buttons = fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>;
    const approveBtn = Array.from(buttons).find((b) => b.textContent?.includes('Approve'));
    expect(approveBtn).toBeTruthy();
    approveBtn!.click();
    await new Promise((r) => setTimeout(r, 0));
    const post = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/approval/`);
    expect(post.request.method).toBe('POST');
    expect(post.request.body).toEqual({ decision: 'approved', rationale: undefined });
    post.flush({ ...INVOICE, status: 'approved' });
    await fixture.whenStable();
    fixture.detectChanges();
    const after = fixture.nativeElement.textContent as string;
    expect(after).toContain('approved');
    // Terminal state: no approve/reject/evaluate buttons remain.
    expect(actionLabels(fixture)).toEqual([]);
  });

  it('hides actions for non-approver roles on a pending invoice', async () => {
    const fixture = setup('OPERATOR');
    const req = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
    req.flush({ ...INVOICE, status: 'pending_approval' });
    const decision = http.expectOne(DECISION_URL);
    decision.flush({
      result: 'escalated',
      reason_code: 'amount_exceeds_escalation_threshold',
      reason_detail: 'Amount exceeds the escalation threshold.',
      policy_version: 1,
    });
    await fixture.whenStable();
    fixture.detectChanges();
    // An OPERATOR (evaluator) has no approve/evaluate action on a pending invoice.
    expect(actionLabels(fixture)).toEqual([]);
  });

  it('shows no actions on terminal states for any role', async () => {
    for (const role of ['OPERATOR', 'APPROVER', 'FINANCE_ADMIN']) {
      const fixture = setup(role);
      const req = http.expectOne(`${API}/organizations/${ORG}/invoices/${ID}/`);
      req.flush({ ...INVOICE, status: 'approved' });
      const decision = http.expectOne(DECISION_URL);
      decision.flush({
        result: 'approved',
        reason_code: 'policy_ok',
        reason_detail: 'The invoice complies with the active policy.',
        policy_version: 1,
      });
      await fixture.whenStable();
      fixture.detectChanges();
      expect(actionLabels(fixture)).toEqual([]);
      fixture.destroy();
    }
  });
});
