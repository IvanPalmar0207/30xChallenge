import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideRouter, Router, Routes } from '@angular/router';

import { environment } from '../../../environments/environment';

import { LoginPage } from './login';

@Component({
  selector: 'pb-landing-stub',
  template: '<p>landing stub</p>',
})
class LandingStub {}

const routes: Routes = [
  { path: '', component: LandingStub },
  { path: 'login', component: LoginPage },
  { path: 'app', component: LandingStub },
  { path: 'app/organizations', component: LandingStub },
  { path: 'app/admin/organizations', component: LandingStub },
];

describe('LoginPage', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LoginPage, LandingStub],
      providers: [
        provideRouter(routes),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('shows a secondary "Back to home" action below the sign-in button', () => {
    const router = TestBed.inject(Router);
    router.navigateByUrl('/login');
    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const back = el.querySelector<HTMLAnchorElement>('a.login__back');
    expect(back).toBeTruthy();
    expect(back?.textContent?.trim()).toBe('Back to home');
    expect(back?.getAttribute('href')).toBe('/');
  });

  it('navigates to the public landing when the back link is clicked', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/login');
    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const back = el.querySelector<HTMLAnchorElement>('a.login__back');
    expect(back).toBeTruthy();

    back!.click();
    await new Promise((r) => setTimeout(r, 0));
    expect(router.url).toBe('/');
  });

  it('keeps the login form untouched and the back link outside the form', () => {
    const router = TestBed.inject(Router);
    router.navigateByUrl('/login');
    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const form = el.querySelector('form');
    const back = el.querySelector<HTMLAnchorElement>('a.login__back');
    expect(form).toBeTruthy();
    expect(form?.contains(back)).toBe(false);
    expect(el.querySelector('button[type="submit"]')).toBeTruthy();
  });

  it('routes a global superadmin WITHOUT memberships to Global administration', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/login');
    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();

    setField(fixture, 'input[type="email"]', 'admin@global.test');
    setField(fixture, 'input[type="password"]', 'secret');
    fixture.detectChanges();

    submitLoginForm(fixture);
    await flushLoginFlow(http, false, true);
    fixture.detectChanges();

    await new Promise((r) => setTimeout(r, 0));
    expect(router.url).toBe('/app/admin/organizations');
  });

  it('routes a non-admin user WITHOUT memberships to Organizations', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/login');
    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();

    setField(fixture, 'input[type="email"]', 'plain@global.test');
    setField(fixture, 'input[type="password"]', 'secret');
    fixture.detectChanges();

    submitLoginForm(fixture);
    await flushLoginFlow(http, false, false);
    fixture.detectChanges();

    await new Promise((r) => setTimeout(r, 0));
    expect(router.url).toBe('/app/organizations');
  });

  it('routes a user WITH memberships to the dashboard /app after login', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/login');
    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();

    setField(fixture, 'input[type="email"]', 'member@company.test');
    setField(fixture, 'input[type="password"]', 'secret');
    fixture.detectChanges();

    submitLoginForm(fixture);
    await flushLoginFlow(http, true);
    fixture.detectChanges();

    await new Promise((r) => setTimeout(r, 0));
    expect(router.url).toBe('/app');
  });
});

function submitLoginForm(fixture: ComponentFixture<LoginPage>): void {
  const form = (fixture.nativeElement as HTMLElement).querySelector<HTMLFormElement>(
    'form.login__form',
  )!;
  form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
}

function setField(
  fixture: ComponentFixture<LoginPage>,
  selector: string,
  value: string,
): void {
  const input = (fixture.nativeElement as HTMLElement).querySelector(
    selector,
  ) as HTMLInputElement;
  input.value = value;
  input.dispatchEvent(new Event('input'));
}

async function flushLoginFlow(
  http: HttpTestingController,
  withMembership = false,
  isGlobalAdmin = false,
): Promise<void> {
  const API = environment.apiBaseUrl;
  const login = http.expectOne(`${API}/auth/login/`);
  login.flush({
    access: 'ACC',
    refresh: 'REF',
    user: { id: 'u1', username: 'u', email: 'u', first_name: '', last_name: '' },
  });
  // Let the async login pipeline advance before /auth/me/ is issued
  // (mirrors the auth.service.spec pattern).
  await new Promise((r) => setTimeout(r, 0));
  const me = http.expectOne(`${API}/auth/me/`);
  me.flush({
    id: 'u1',
    username: 'u',
    email: 'u',
    first_name: '',
    last_name: '',
    is_global_admin: isGlobalAdmin,
    memberships: withMembership
      ? [{ organization_id: 'o1', organization_name: 'Org', role: 'FINANCE_ADMIN' }]
      : [],
  });
  return Promise.resolve();
}
