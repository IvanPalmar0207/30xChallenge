import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';

import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

const API = environment.apiBaseUrl;

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('login stores tokens, loads /me and marks authed with memberships', async () => {
    const promise = service.login('a@b.co', 'pass123');
    const req = http.expectOne(`${API}/auth/login/`);
    expect(req.request.body).toEqual({ email: 'a@b.co', password: 'pass123' });
    req.flush({
      access: 'ACC',
      refresh: 'REF',
      user: { id: 'u1', username: 'a@b.co', email: 'a@b.co', first_name: '', last_name: '' },
    });
    await new Promise((r) => setTimeout(r, 0));
    const me = http.expectOne(`${API}/auth/me/`);
    me.flush({
      id: 'u1', username: 'a@b.co', email: 'a@b.co', first_name: '', last_name: '',
      memberships: [{ organization_id: 'o1', organization_name: 'Ledger Org', role: 'FINANCE_ADMIN' }],
    });
    await promise;
    expect(service.accessToken()).toBe('ACC');
    expect(service.isAuthed()).toBe(true);
    expect(service.user()?.email).toBe('a@b.co');
    expect(service.user()?.memberships?.[0]?.role).toBe('FINANCE_ADMIN');
  });

  it('login failure leaves the state as guest', async () => {
    const promise = service.login('a@b.co', 'wrong');
    const req = http.expectOne(`${API}/auth/login/`);
    req.flush({ detail: 'Invalid email or password.' }, { status: 401, statusText: 'Unauthorized' });
    await expect(promise).rejects.toBeTruthy();
    expect(service.isAuthed()).toBe(false);
    expect(service.status()).toBe('guest');
  });

  it('restore() refreshes via cookie and loads /me', async () => {
    const promise = service.restore();
    const refresh = http.expectOne(`${API}/auth/refresh/`);
    refresh.flush({ access: 'ACC2' });
    await new Promise((r) => setTimeout(r, 0));
    const me = http.expectOne(`${API}/auth/me/`);
    me.flush({
      id: 'u1',
      username: 'a@b.co',
      email: 'a@b.co',
      first_name: '',
      last_name: '',
      memberships: [
        { organization_id: 'o1', organization_name: 'Ledger Org', role: 'OPERATOR' },
      ],
    });
    await expect(promise).resolves.toBe(true);
    expect(service.accessToken()).toBe('ACC2');
    expect(service.isAuthed()).toBe(true);
    expect(service.currentMembership()?.organization_name).toBe('Ledger Org');
  });

  it('restore() without a valid refresh goes to guest', async () => {
    const promise = service.restore();
    const refresh = http.expectOne(`${API}/auth/refresh/`);
    refresh.flush({ detail: 'expired' }, { status: 401, statusText: 'Unauthorized' });
    await expect(promise).resolves.toBe(false);
    expect(service.status()).toBe('guest');
    expect(service.accessToken()).toBeNull();
  });

  it('logout calls the endpoint and clears state', async () => {
    service['accessToken'].set('ACC');
    service['user'].set({ id: 'u1', username: 'a@b.co', email: 'a@b.co', first_name: '', last_name: '' });
    service['status'].set('authed');
    const promise = service.logout();
    const req = http.expectOne(`${API}/auth/logout/`);
    req.flush('', { status: 204, statusText: 'No Content' });
    await promise;
    expect(service.accessToken()).toBeNull();
    expect(service.isAuthed()).toBe(false);
  });

  it('single-flight refresh is shared across callers', async () => {
    const first = service.refreshOnce();
    const second = service.refreshOnce();
    const req = http.expectOne(`${API}/auth/refresh/`);
    req.flush({ access: 'ACC3' });
    await expect(first).resolves.toBe(true);
    await expect(second).resolves.toBe(true);
    http.expectNone(`${API}/auth/refresh/`);
  });
});