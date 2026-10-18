import { TestBed } from '@angular/core/testing';
import { ComponentFixture } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { ActivatedRoute, convertToParamMap } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { OrganizationsMembersPage } from './organizations-members';
import { environment } from '../../../environments/environment';

const API = environment.apiBaseUrl;
const ORG = 'org-1';

function buttons(el: HTMLElement): HTMLButtonElement[] {
  return Array.from(el.querySelectorAll('button'));
}

describe('OrganizationsMembersPage', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<OrganizationsMembersPage>;
  let auth: AuthService;
  let originalConfirm: ((message?: string) => boolean) | undefined;
  let clipboardMock: { writeText: ReturnType<typeof vi.fn> } | undefined;

  beforeEach(async () => {
    originalConfirm = window.confirm;
    window.confirm = () => true;
    clipboardMock = { writeText: vi.fn().mockResolvedValue(undefined) };
    Object.defineProperty(window, 'location', {
      value: { origin: 'http://127.0.0.1:4200' },
      writable: true,
    });
    Object.defineProperty(window.navigator, 'clipboard', {
      value: clipboardMock,
      configurable: true,
    });

    await TestBed.configureTestingModule({
      imports: [OrganizationsMembersPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ id: ORG }) } },
        },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
    fixture = TestBed.createComponent(OrganizationsMembersPage);
    fixture.detectChanges();
  });

  afterEach(() => {
    if (originalConfirm !== undefined) window.confirm = originalConfirm;
    http.verify();
  });

  function flushLoad(memberships: Record<string, unknown>[] = [], orgName = 'Org 1'): void {
    http
      .expectOne((r) => r.url.includes(`/organizations/${ORG}/memberships/`))
      .flush(memberships);
    http.expectOne(`${API}/organizations/${ORG}/`).flush({
      id: ORG,
      name: orgName,
      status: 'active',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });
    fixture.detectChanges();
  }

  async function openCreateForm(): Promise<void> {
    const el = fixture.nativeElement as HTMLElement;
    const email = el.querySelector<HTMLInputElement>('#create_email')!;
    email.value = 'New@Example.com';
    email.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  /// After clicking "Create user" and flushing, auto-invite is issued.
  async function createUserFlow(): Promise<void> {
    await openCreateForm();
    const el = fixture.nativeElement as HTMLElement;
    buttons(el).find((b) => b.textContent?.includes('Create user'))!.click();

    http.expectOne(`${API}/organizations/${ORG}/users/`).flush(
      { id: 1, email: 'new@example.com', role: 'OPERATOR', membership_id: 'm9' },
      { status: 201, statusText: 'Created' },
    );
    flushLoad([]);
    flushInvite('TOK');
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();
  }

  function flushInvite(token = 'TOK'): void {
    http.expectOne(`${API}/organizations/${ORG}/users/1/invite/`).flush(
      { setup_token: token, expires_at: '2026-01-04T00:00:00Z' },
      { status: 201, statusText: 'Created' },
    );
  }

  it('shows the forbidden state on 404', () => {
    http
      .expectOne((r) => r.url.includes(`/organizations/${ORG}/memberships/`))
      .flush({}, { status: 404, statusText: 'Not found' });
    http.expectOne(`${API}/organizations/${ORG}/`).flush({}, {
      status: 404,
      statusText: 'Not found',
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No permission');
  });

  it('lists members and offers issue-setup and role/activity actions', () => {
    flushLoad([
      {
        id: 'm1',
        user: { id: 1, username: 'a@x.test', email: 'a@x.test' },
        role: 'FINANCE_ADMIN',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 'm2',
        user: { id: 2, username: 'b@x.test', email: 'b@x.test' },
        role: 'OPERATOR',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ]);
    const text = fixture.nativeElement.textContent ?? '';
    expect(text).toContain('Organization members');
    expect(text).toContain('a@x.test');
    expect(text).toContain('b@x.test');
    expect(text).toContain('Issue setup link');
    const roleSelects = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('select.role-select'),
    );
    expect(roleSelects.length).toBe(1);
  });

  it('filters out the current actor row (no self-actions in the table)', () => {
    // The session user is id 7; the table must not render BOTH copies of that
    // membership — the actor row is hidden, others remain.
    // UserProfile.id is a string in the frontend model; the filter compares
    // String(m.user.id) !== selfId, so '7' matches membership user.id 7.
    auth['user'].set({
      id: '7', username: 'actor', email: 'actor@x.test', first_name: '', last_name: '',
      memberships: [{ organization_id: ORG, organization_name: 'Org 1', role: 'FINANCE_ADMIN' }],
    });
    fixture.detectChanges();
    flushLoad([
      {
        id: 'm7',
        user: { id: 7, username: 'actor@x.test', email: 'actor@x.test' },
        role: 'FINANCE_ADMIN',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 'm2',
        user: { id: 2, username: 'b@x.test', email: 'b@x.test' },
        role: 'OPERATOR',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ]);
    const rows = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('tbody tr'),
    );
    expect(rows.length).toBe(1);
    const html = fixture.nativeElement.innerHTML;
    expect(html).toContain('b@x.test');
    expect(html).not.toContain('>actor@x.test<');
  });

  it('after creating a user shows post-creation instructions and the panel', async () => {
    fixture.detectChanges();
    flushLoad([]);
    await createUserFlow();

    const text = fixture.nativeElement.textContent ?? '';
    expect(text).toContain('User created successfully');
    expect(text).toContain('Password setup link');
    expect(text).toContain('expires in 72 hours');
    expect(text).toContain('Copy link');
    expect(text).toContain('Show link');
    expect(text).toContain('Close');
    expect(text).toContain('Generate new link');
  });

  it('copies the FULL link value (not the truncated text)', async () => {
    fixture.detectChanges();
    flushLoad([]);
    await createUserFlow();

    const displayed = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>(
      '.setup-link__value',
    )!;
    expect(displayed.value).not.toContain('TOK');

    const copyButton = buttons(fixture.nativeElement as HTMLElement).find(
      (b) => b.textContent?.includes('Copy link'),
    )!;
    copyButton.click();
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();

    expect(clipboardMock!.writeText).toHaveBeenCalledWith(
      'http://127.0.0.1:4200/setup-account?token=TOK',
    );
    expect(fixture.nativeElement.textContent).toContain('Link copied');
  });

  it('handles clipboard failures without blocking the screen', async () => {
    fixture.detectChanges();
    flushLoad([]);
    await createUserFlow();

    clipboardMock!.writeText.mockRejectedValueOnce(new Error('denied'));
    const copyButton = buttons(fixture.nativeElement as HTMLElement).find(
      (b) => b.textContent?.includes('Copy link'),
    )!;
    copyButton.click();
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent ?? '';
    expect(text).toContain('copy it manually');
    expect(text).not.toContain('Link copied');
  });

  it('shows and hides the link with the mask toggling', async () => {
    fixture.detectChanges();
    flushLoad([]);
    await createUserFlow();

    const toggle = buttons(fixture.nativeElement as HTMLElement).find(
      (b) => b.textContent?.includes('Show link'),
    )!;
    toggle.click();
    fixture.detectChanges();
    const shown = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>(
      '.setup-link__value',
    )!;
    expect(shown.value).toContain('token=TOK');
  });

  it('closing the panel discards the token from the interface', async () => {
    fixture.detectChanges();
    flushLoad([]);
    await createUserFlow();

    expect(fixture.nativeElement.textContent).toContain('Password setup link');
    const close = buttons(fixture.nativeElement as HTMLElement).find(
      (b) => b.textContent?.includes('Close'),
    )!;
    close.click();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent ?? '';
    expect(text).not.toContain('Password setup link');
    expect(text).not.toContain('setup-account?token=');
    expect(text).not.toContain('TOK');
  });

  it('does not invent a link when generation fails; shows the honest state', async () => {
    fixture.detectChanges();
    flushLoad([]);
    await openCreateForm();
    buttons(fixture.nativeElement as HTMLElement)
      .find((b) => b.textContent?.includes('Create user'))!
      .click();

    http.expectOne(`${API}/organizations/${ORG}/users/`).flush(
      { id: 1, email: 'new@example.com', role: 'OPERATOR', membership_id: 'm9' },
      { status: 201, statusText: 'Created' },
    );
    flushLoadSilent();
    http
      .expectOne(`${API}/organizations/${ORG}/users/1/invite/`)
      .flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent ?? '';
    expect(text).toContain('User created, but access is not ready');
    expect(text).not.toContain('setup-account?token=');
    expect(text).not.toContain('TOK');
  });

  function flushLoadSilent(): void {
    http
      .expectOne((r) => r.url.includes(`/organizations/${ORG}/memberships/`))
      .flush([]);
    http.expectOne(`${API}/organizations/${ORG}/`).flush({
      id: ORG,
      name: 'Org 1',
      status: 'active',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });
  }

  it('shows a friendly message when the email is already registered', async () => {
    fixture.detectChanges();
    flushLoad([]);
    await openCreateForm();
    // Change to a duplicate email.
    const email = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>(
      '#create_email',
    )!;
    email.value = 'dup@example.com';
    email.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    buttons(fixture.nativeElement as HTMLElement)
      .find((b) => b.textContent?.includes('Create user'))!
      .click();

    http
      .expectOne(`${API}/organizations/${ORG}/users/`)
      .flush(
        { email: ['A user with this email already exists.'] },
        { status: 400, statusText: 'Bad Request' },
      );
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent ?? '';
    expect(text).toContain('This email is already registered');
  });

  it('asks for confirmation and identifies the user before issuing a row link', async () => {
    fixture.detectChanges();
    flushLoad([
      {
        id: 'm2',
        user: { id: 2, username: 'b@x.test', email: 'b@x.test' },
        role: 'OPERATOR',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ]);

    const el = fixture.nativeElement as HTMLElement;
    const issueButton = buttons(el).find(
      (b) => b.textContent?.includes('Issue setup link'),
    )!;
    issueButton.click();
    fixture.detectChanges();

    // Inline confirmation opens with the matching email BEFORE any request.
    const confirmText = fixture.nativeElement.textContent ?? '';
    expect(confirmText).toContain('Generate setup link');
    expect(confirmText).toContain('for: b@x.test'.replace('for:', 'For:'));
    expect(confirmText).toContain('Cancel');
    const generate = buttons(fixture.nativeElement as HTMLElement).find(
      (b) => b.textContent?.includes('Generate link'),
    )!;
    generate.click();
    fixture.detectChanges();

    http.expectOne(`${API}/organizations/${ORG}/users/2/invite/`).flush(
      { setup_token: 'TOK2', expires_at: '2026-01-05T00:00:00Z' },
      { status: 201, statusText: 'Created' },
    );
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Setup link generated');
    // Panel identifies the user for which the link was generated.
    expect(fixture.nativeElement.textContent).toContain('b@x.test');
  });

  it('cancelling the inline confirmation does not issue the link', async () => {
    fixture.detectChanges();
    flushLoad([
      {
        id: 'm2',
        user: { id: 2, username: 'b@x.test', email: 'b@x.test' },
        role: 'OPERATOR',
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ]);

    const issueButton = buttons(fixture.nativeElement as HTMLElement).find(
      (b) => b.textContent?.includes('Issue setup link'),
    )!;
    issueButton.click();
    fixture.detectChanges();
    buttons(fixture.nativeElement as HTMLElement)
      .find((b) => b.textContent?.includes('Cancel'))!
      .click();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent ?? '';
    expect(text).not.toContain('Password setup link');
    expect(text).not.toContain('setup-account?token=');
  });

  it('asks for confirmation before regenerating the link', async () => {
    const confirmed = vi.fn(() => false);
    window.confirm = confirmed;

    fixture.detectChanges();
    flushLoad([]);
    await createUserFlow();

    const regen = buttons(fixture.nativeElement as HTMLElement).find(
      (b) => b.textContent?.includes('Generate new link'),
    )!;
    regen.click();
    fixture.detectChanges();
    expect(confirmed).toHaveBeenCalledTimes(1);

    window.confirm = () => true;
    regen.click();
    fixture.detectChanges();
    http.expectOne(`${API}/organizations/${ORG}/users/1/invite/`).flush(
      { setup_token: 'NEWTOK2', expires_at: '2026-01-05T00:00:00Z' },
      { status: 201, statusText: 'Created' },
    );
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('New setup link generated');
  });

  it('lets the empty state offer to create the first user', async () => {
    fixture.detectChanges();
    flushLoad([]);
    const text = fixture.nativeElement.textContent ?? '';
    expect(text).toContain('No members in this organization yet');
    expect(text).toContain('Create first user');
  });

  it('shows the load-error state with a Retry action', async () => {
    http
      .expectOne((r) => r.url.includes(`/organizations/${ORG}/memberships/`))
      .flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
    // The parallel org-name lookup also fires; give it any response so no
    // request stays open for verify().
    http.expectOne(`${API}/organizations/${ORG}/`).flush({}, {
      status: 500,
      statusText: 'Server Error',
    });
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent ?? '';
    expect(text).toContain('We could not load members');
    expect(text).toContain('Retry');
    expect(text).not.toContain('No members in this organization yet');
  });
});