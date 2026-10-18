import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { vi } from 'vitest';

import { apiInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

const API = environment.apiBaseUrl;

describe('apiInterceptor', () => {
  let http: HttpTestingController;
  let auth: AuthService;
  let httpClient: HttpClient;
  let router: Router;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
    httpClient = TestBed.inject(HttpClient);
    router = TestBed.inject(Router);
  });

  afterEach(() => http.verify());

  it('attaches Bearer only to API requests', async () => {
    auth['accessToken'].set('TKN');
    const api$ = firstValueFrom(httpClient.get(`${API}/auth/me/`));
    const external$ = firstValueFrom(httpClient.get('https://other.example/data'));
    const apiReq = http.expectOne(`${API}/auth/me/`);
    const extReq = http.expectOne('https://other.example/data');
    expect(apiReq.request.headers.get('Authorization')).toBe('Bearer TKN');
    expect(apiReq.request.withCredentials).toBe(true);
    expect(extReq.request.headers.has('Authorization')).toBe(false);
    expect(extReq.request.withCredentials).toBeFalsy();
    apiReq.flush({ id: 'u' });
    extReq.flush({ ok: true });
    await Promise.all([api$, external$]);
  });

  it('401 triggers one refresh and retries the original request', async () => {
    auth['accessToken'].set('OLD');
    const request$ = firstValueFrom(httpClient.get(`${API}/auth/me/`));
    const first = http.expectOne(`${API}/auth/me/`);
    first.flush({}, { status: 401, statusText: 'Unauthorized' });
    const refresh = http.expectOne(`${API}/auth/refresh/`);
    refresh.flush({ access: 'NEW' });
    await new Promise((r) => setTimeout(r, 0));
    const retry = http.expectOne(`${API}/auth/me/`);
    expect(retry.request.headers.get('Authorization')).toBe('Bearer NEW');
    retry.flush({ id: 'u1' });
    await expect(request$).resolves.toBeTruthy();
  });

  it('401 with failed refresh navigates to login without infinite retries', async () => {
    auth['accessToken'].set('OLD');
    const spy = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    const request$ = firstValueFrom(httpClient.get(`${API}/auth/me/`));
    const first = http.expectOne(`${API}/auth/me/`);
    first.flush({}, { status: 401, statusText: 'Unauthorized' });
    const refresh = http.expectOne(`${API}/auth/refresh/`);
    refresh.flush({ detail: 'nope' }, { status: 401, statusText: 'Unauthorized' });
    await expect(request$).rejects.toBeTruthy();
    expect(spy).toHaveBeenCalledWith(['/login']);
    http.expectNone(`${API}/auth/me/`);
  });

  it('403 is not treated as a session problem', async () => {
    auth['accessToken'].set('OLD');
    const request$ = firstValueFrom(httpClient.get(`${API}/auth/me/`));
    const req = http.expectOne(`${API}/auth/me/`);
    req.flush({ detail: 'Forbidden' }, { status: 403, statusText: 'Forbidden' });
    await expect(request$).rejects.toBeTruthy();
    http.expectNone(`${API}/auth/refresh/`);
  });

  it('never refreshes for /auth/login/ 401', async () => {
    const request$ = firstValueFrom(
      httpClient.post(`${API}/auth/login/`, { email: 'x', password: 'y' }),
    );
    const req = http.expectOne(`${API}/auth/login/`);
    req.flush({ detail: 'x' }, { status: 401, statusText: 'Unauthorized' });
    await expect(request$).rejects.toBeTruthy();
    http.expectNone(`${API}/auth/refresh/`);
  });
});