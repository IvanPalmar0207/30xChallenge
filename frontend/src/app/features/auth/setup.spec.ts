import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ComponentFixture } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter, Router, Routes } from '@angular/router';

import { SetupAccountPage } from './setup';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'pb-login-stub',
  template: '<p>login stub</p>',
})
class LoginStub {}

const routes: Routes = [
  { path: '', component: LoginStub },
  { path: 'login', component: LoginStub },
  { path: 'setup-account', component: SetupAccountPage },
];

describe('SetupAccountPage', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<SetupAccountPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SetupAccountPage, LoginStub],
      providers: [
        provideRouter(routes),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  async function createFixture(token: string): Promise<ComponentFixture<SetupAccountPage>> {
    const router = TestBed.inject(Router);
    await router.navigateByUrl(`/setup-account?token=${token}`);
    const f = TestBed.createComponent(SetupAccountPage);
    f.detectChanges();
    return f;
  }

  function passwordInputs(
    f: ComponentFixture<SetupAccountPage>,
  ): HTMLInputElement[] {
    return Array.from(
      (f.nativeElement as HTMLElement).querySelectorAll('input[type="password"]'),
    ) as HTMLInputElement[];
  }

  function setValue(f: ComponentFixture<SetupAccountPage>, index: number, value: string): void {
    const input = passwordInputs(f)[index];
    input.value = value;
    input.dispatchEvent(new Event('input'));
    f.detectChanges();
  }

  function submit(f: ComponentFixture<SetupAccountPage>): void {
    const form = (f.nativeElement as HTMLElement).querySelector<HTMLFormElement>('form')!;
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    f.detectChanges();
  }

  it('submits the token and password and reaches the success state', async () => {
    fixture = await createFixture('raw-token-xyz');
    setValue(fixture, 0, 'NewStrongPass456!');
    setValue(fixture, 1, 'NewStrongPass456!');
    submit(fixture);

    const req = http.expectOne(`${environment.apiBaseUrl}/auth/set-password/`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      setup_token: 'raw-token-xyz',
      password: 'NewStrongPass456!',
    });
    req.flush(null, { status: 204, statusText: 'No Content' });
    await fixture.whenStable();
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Password set successfully');
    expect(text).toContain('Go to sign in');
  });

  it('disables the button when passwords do not match', async () => {
    fixture = await createFixture('raw-token-xyz');
    setValue(fixture, 0, 'PasswordOne123!');
    setValue(fixture, 1, 'PasswordTwo123!');
    const submitButton = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('button[type="submit"]'),
    )[0] as HTMLButtonElement;
    expect(submitButton.disabled).toBe(true);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Passwords do not match.');
  });

  it('shows a clear error when the backend rejects the token', async () => {
    fixture = await createFixture('bad-token-abc');
    setValue(fixture, 0, 'NewStrongPass456!');
    setValue(fixture, 1, 'NewStrongPass456!');
    submit(fixture);

    const req = http.expectOne(`${environment.apiBaseUrl}/auth/set-password/`);
    req.flush(
      { detail: 'Invalid or expired setup token.' },
      { status: 400, statusText: 'Bad Request' },
    );
    await fixture.whenStable();
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('We could not validate the link');
    expect(text).toContain('already used');
  });

  it('shows a connection message on network failure, without internals', async () => {
    fixture = await createFixture('net-token-xyz');
    setValue(fixture, 0, 'NewStrongPass456!');
    setValue(fixture, 1, 'NewStrongPass456!');
    submit(fixture);

    const req = http.expectOne(`${environment.apiBaseUrl}/auth/set-password/`);
    req.flush({}, { status: 0, statusText: 'Unknown Error' });
    await fixture.whenStable();
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('connection problem');
  });

  it('toggles password visibility with accessible controls', async () => {
    fixture = await createFixture('raw-token-xyz');
    setValue(fixture, 0, 'NewStrongPass456!');
    setValue(fixture, 1, 'NewStrongPass456!');

    const toggle = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('button.password-toggle'),
    )[0] as HTMLButtonElement;
    toggle.click();
    fixture.detectChanges();
    const inputsAfterShow = (fixture.nativeElement as HTMLElement).querySelectorAll(
      'input[type="text"]',
    );
    expect(inputsAfterShow.length).toBeGreaterThan(0);
    expect(toggle.getAttribute('aria-pressed')).toBe('true');
  });

  it('does not call the backend when there is no token in the URL', async () => {
    fixture = await createFixture('');
    setValue(fixture, 0, 'NewStrongPass456!');
    setValue(fixture, 1, 'NewStrongPass456!');
    submit(fixture);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('We could not validate the link');
  });

  it('does not send a duplicate when the submit button is pressed repeatedly', async () => {
    fixture = await createFixture('dup-token-xyz');
    setValue(fixture, 0, 'NewStrongPass456!');
    setValue(fixture, 1, 'NewStrongPass456!');
    submit(fixture);
    // Press again while loading: no second HTTP request is issued.
    submit(fixture);

    const req = http.expectOne(`${environment.apiBaseUrl}/auth/set-password/`);
    req.flush(null, { status: 204, statusText: 'No Content' });
    await fixture.whenStable();
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Password set successfully',
    );
  });
});