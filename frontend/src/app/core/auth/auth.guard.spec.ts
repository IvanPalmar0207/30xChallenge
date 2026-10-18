import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  Router,
  provideRouter,
  UrlTree,
  ActivatedRouteSnapshot,
  type RouterStateSnapshot,
} from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';

import { authGuard } from './auth.guard';
import { apiInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

const API = environment.apiBaseUrl;

@Component({ template: '' })
class Dummy {}

function call(): Promise<boolean | UrlTree> {
  const route = new ActivatedRouteSnapshot() as never;
  const state = { url: '/app' } as RouterStateSnapshot;
  return TestBed.runInInjectionContext(
    () => authGuard(route, state) as Promise<boolean | UrlTree>,
  );
}

describe('authGuard', () => {
  let auth: AuthService;
  let http: HttpTestingController;
  let router: Router;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      imports: [Dummy],
      providers: [
        provideRouter([{ path: 'login', component: Dummy }]),
        provideHttpClient(withInterceptors([apiInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
  });

  afterEach(() => http.verify());

  it('denies guests with a redirect to /login', async () => {
    auth.clear(); // guest: no network calls expected
    const result = await call();
    expect(result).toBeInstanceOf(UrlTree);
    expect(router.serializeUrl(result as UrlTree)).toContain('/login');
    http.expectNone(`${API}/auth/refresh/`);
  });

  it('allows an authenticated user without network calls', async () => {
    auth['accessToken'].set('T');
    auth['user'].set({ id: 'u', username: 'u@c.com', email: 'u@c.com', first_name: '', last_name: '' });
    auth['status'].set('authed');
    await expect(call()).resolves.toBe(true);
    http.expectNone(`${API}/auth/refresh/`);
  });

  it('restores a session during "restoring" before deciding', async () => {
    const resultPromise = call();
    const refresh = http.expectOne(`${API}/auth/refresh/`);
    refresh.flush({ access: 'R1' });
    await new Promise((r) => setTimeout(r, 0));
    const me = http.expectOne(`${API}/auth/me/`);
    me.flush({ id: 'u', username: 'u@c.com', email: 'u@c.com', first_name: '', last_name: '' });
    await expect(resultPromise).resolves.toBe(true);
    expect(auth.isAuthed()).toBe(true);
  });

  it('redirects to login when restoration fails', async () => {
    const resultPromise = call();
    const refresh = http.expectOne(`${API}/auth/refresh/`);
    refresh.flush({ detail: 'no' }, { status: 401, statusText: 'Unauthorized' });
    await expect(resultPromise).resolves.toBeTruthy();
    const result = await resultPromise;
    expect(result).toBeInstanceOf(UrlTree);
  });
});