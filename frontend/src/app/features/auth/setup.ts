import { Component, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';

import { Icon } from '../../shared/icon';
import { Logo } from '../../shared/logo';
import { AuthService } from '../../core/auth/auth.service';

type SetupState = 'idle' | 'loading' | 'success' | 'error';

/**
 * Initial password setup — public page for a user invited with a one-time
 * setup token (e.g. /setup-account?token=...). Validates locally (required,
 * confirmation match, minimal length), submits only {setup_token, password}
 * to the backend, and never stores the token nor the credentials.
 *
 * Error handling is deliberately uniform: the backend answers the same 400
 * for an invalid, expired, used, or inactive-account token, so this page
 * never distinguishes between those cases (no account enumeration).
 */
@Component({
  selector: 'pb-setup-account',
  imports: [FormsModule, RouterLink, Logo, Icon],
  template: `
    <main class="login">
      <section class="login__card" aria-labelledby="setup-title">
        <a routerLink="/" class="login__brand" aria-label="Back to PayBlood home">
          <pb-logo />
        </a>

        <h1 id="setup-title" class="login__title">Set your password</h1>
        <p class="login__lede">
          Complete this step to access PayBlood. Create a secure password and
          confirm it. Afterwards you can sign in with your email and the
          password you choose.
        </p>

        @if (state() === 'success') {
          <div class="setup__success" role="status">
            <h2 class="setup__success-title">Password set successfully</h2>
            <p class="setup__success-text">
              Your account is ready. You can now sign in to PayBlood with
              your email and your new password.
            </p>
            <a routerLink="/login" class="pb-btn pb-btn--primary setup__success-link">
              Go to sign in
            </a>
          </div>
        } @else {
          <form
            #form="ngForm"
            class="login__form"
            (ngSubmit)="submit()"
            novalidate
          >
            <div class="field">
              <label for="password" class="field__label">New password</label>
              <div class="field__row">
                <input
                  id="password"
                  name="password"
                  type="{{ showPassword() ? 'text' : 'password' }}"
                  required
                  minlength="8"
                  autocomplete="new-password"
                  placeholder="At least 8 characters"
                  [(ngModel)]="password"
                  aria-describedby="password-hint"
                />
                <button
                  type="button"
                  class="password-toggle"
                  (click)="togglePassword()"
                  [attr.aria-pressed]="showPassword()"
                  [attr.aria-label]="showPassword() ? 'Hide password' : 'Show password'"
                >
                  {{ showPassword() ? 'Hide' : 'Show' }}
                </button>
              </div>
              <p id="password-hint" class="field__hint">
                Use at least 8 characters. The server enforces the full
                password policy.
              </p>
              @if (fieldError() === 'password') {
                <p class="field__error" role="alert">{{ error() }}</p>
              }
            </div>

            <div class="field">
              <label for="passwordConfirm" class="field__label">Confirm password</label>
              <div class="field__row">
                <input
                  id="passwordConfirm"
                  name="passwordConfirm"
                  type="{{ showConfirmPassword() ? 'text' : 'password' }}"
                  required
                  autocomplete="new-password"
                  placeholder="Repeat your password"
                  [(ngModel)]="passwordConfirm"
                />
                <button
                  type="button"
                  class="password-toggle"
                  (click)="toggleConfirmPassword()"
                  [attr.aria-pressed]="showConfirmPassword()"
                  [attr.aria-label]="showConfirmPassword() ? 'Hide confirm password' : 'Show confirm password'"
                >
                  {{ showConfirmPassword() ? 'Hide' : 'Show' }}
                </button>
              </div>
              @if (passwordConfirmValue.length > 0 && !passwordsMatch()) {
                <p class="field__error" role="alert">Passwords do not match.</p>
              } @else if (fieldError() === 'confirm') {
                <p class="field__error" role="alert">{{ error() }}</p>
              }
            </div>

            @if (state() === 'error' && fieldError() === null) {
              <p class="login__error" role="alert" [attr.aria-live]="'polite'">
                {{ error() }}
              </p>
            }

            <button
              type="submit"
              class="pb-btn pb-btn--primary login__submit"
              [disabled]="state() === 'loading' || !canSubmit()"
            >
              @if (state() === 'loading') {
                <pb-icon name="loader" [spin]="true" />
                Setting password…
              } @else {
                Set password
              }
            </button>
          </form>
        }
      </section>
    </main>
  `,
  styles: `
    .login {
      min-height: 100dvh;
      display: grid;
      place-items: center;
      padding: var(--pb-space-5);
      background:
        repeating-linear-gradient(
          to bottom,
          transparent 0,
          transparent 46px,
          color-mix(in srgb, var(--pb-line) 60%, transparent) 46px,
          color-mix(in srgb, var(--pb-line) 60%, transparent) 47px
        ),
        var(--pb-bg);
    }

    .login__card {
      width: 100%;
      max-width: 440px;
      background: var(--pb-surface);
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-l);
      box-shadow: var(--pb-shadow-card);
      padding: var(--pb-space-6);
    }

    .login__brand {
      display: inline-block;
      text-decoration: none;
    }

    .login__title {
      margin-top: var(--pb-space-5);
      font-size: 1.5rem;
      letter-spacing: -0.03em;
    }

    .login__lede {
      margin-top: var(--pb-space-1);
      color: var(--pb-ink-soft);
      font-size: var(--pb-text-sm);
    }

    .login__form {
      margin-top: var(--pb-space-5);
      display: grid;
      gap: var(--pb-space-4);
    }

    .field {
      display: grid;
      gap: var(--pb-space-1);
    }

    .field__label {
      font-weight: 600;
      font-size: var(--pb-text-sm);
      color: var(--pb-ink-soft);
    }

    .field__row {
      display: flex;
      gap: var(--pb-space-2);
      align-items: center;
    }

    .field input {
      flex: 1;
      min-width: 0;
      padding: 0.625rem 0.8125rem;
      border: 1px solid var(--pb-line-strong);
      border-radius: var(--pb-radius-m);
      background: var(--pb-surface);
      font-size: var(--pb-text-base);
      transition: border-color var(--pb-dur) var(--pb-ease);
    }

    .field input:focus-visible {
      outline: 2px solid var(--pb-focus, var(--pb-accent-strong));
      outline-offset: 1px;
      border-color: transparent;
    }

    .password-toggle {
      padding: 0.4375rem 0.6875rem;
      border: 1px solid var(--pb-line-strong);
      border-radius: var(--pb-radius-m);
      background: transparent;
      color: var(--pb-ink-soft);
      font-size: var(--pb-text-sm);
      font-weight: 600;
      cursor: pointer;
      transition: border-color var(--pb-dur) var(--pb-ease), color var(--pb-dur) var(--pb-ease);
    }

    .password-toggle:focus-visible {
      outline: 2px solid var(--pb-focus, var(--pb-accent-strong));
      outline-offset: 1px;
    }

    .field__hint {
      color: var(--pb-muted);
      font-size: var(--pb-text-xs);
    }

    .field__error {
      color: var(--pb-blocked);
      font-size: var(--pb-text-sm);
    }

    .login__error {
      color: var(--pb-blocked);
      font-size: var(--pb-text-sm);
    }

    .login__submit {
      width: 100%;
    }

    .setup__success {
      margin-top: var(--pb-space-4);
      padding: var(--pb-space-5);
      border: 1px solid var(--pb-approved-bg);
      background: var(--pb-approved-bg);
      border-radius: var(--pb-radius-m);
      color: var(--pb-approved);
    }

    .setup__success-title {
      margin: 0 0 var(--pb-space-1);
      font-size: 1.125rem;
      font-weight: 600;
    }

    .setup__success-text {
      margin: 0 0 var(--pb-space-4);
      font-size: var(--pb-text-sm);
    }

    .setup__success-link {
      width: 100%;
    }

    @media (max-width: 560px) {
      .field__row {
        flex-direction: column;
        align-items: stretch;
      }

      .password-toggle {
        justify-self: start;
      }
    }
  `,
})
export class SetupAccountPage {
  protected readonly password = signal('');
  protected readonly passwordConfirm = signal('');
  protected readonly state = signal<SetupState>('idle');
  protected readonly error = signal('');
  protected readonly showPassword = signal(false);
  protected readonly showConfirmPassword = signal(false);
  /** Which field the current error belongs to: 'password' | 'confirm' | null. */
  protected readonly fieldError = signal<'password' | 'confirm' | null>(null);

  private setupToken: string | null = null;

  constructor(
    private readonly auth: AuthService,
    private readonly router: Router,
    private readonly route: ActivatedRoute,
  ) {
    this.setupToken = this.route.snapshot.queryParamMap.get('token');
    if (this.setupToken) {
      // Remove the token from the URL so it does not linger in history or
      // logs; the value is kept in memory only and never persisted.
      try {
        void this.router.navigate([], {
          queryParams: {},
          replaceUrl: true,
        });
      } catch {
        // Non-fatal: the in-memory copy is what the flow uses.
      }
    }
  }

  protected get passwordValue(): string {
    const value = this.password();
    return value ?? '';
  }

  protected get passwordConfirmValue(): string {
    const value = this.passwordConfirm();
    return value ?? '';
  }

  protected passwordsMatch(): boolean {
    return this.passwordValue === this.passwordConfirmValue;
  }

  protected canSubmit(): boolean {
    return (
      this.setupToken !== null &&
      this.passwordValue.length >= 8 &&
      this.passwordConfirmValue.length > 0 &&
      this.passwordsMatch()
    );
  }

  protected togglePassword(): void {
    this.showPassword.update((v) => !v);
  }

  protected toggleConfirmPassword(): void {
    this.showConfirmPassword.update((v) => !v);
  }

  protected async submit(): Promise<void> {
    const rawToken = this.setupToken;
    if (!rawToken) {
      this.fieldError.set(null);
      this.error.set(
        'We could not validate the link: it is invalid, expired, or already used. ' +
          'Contact the administrator of your organization to recover access.',
      );
      this.state.set('error');
      return;
    }
    if (this.state() === 'loading') return;
    if (this.passwordValue.length < 8) {
      this.fieldError.set('password');
      this.error.set('Password must be at least 8 characters long.');
      return;
    }
    if (!this.passwordsMatch()) {
      this.fieldError.set('confirm');
      this.error.set('Passwords do not match.');
      return;
    }
    this.state.set('loading');
    this.error.set('');
    this.fieldError.set(null);
    try {
      await this.auth.setPassword(rawToken, this.passwordValue);
      this.setupToken = null;
      this.state.set('success');
    } catch (err) {
      this.state.set('error');
      if (err instanceof HttpErrorResponse && err.status === 400) {
        this.fieldError.set(null);
        this.error.set(
          'We could not validate the link. It is invalid, expired, or already used. ' +
            'Contact the administrator of your organization to recover access.',
        );
      } else if (err instanceof HttpErrorResponse && err.status === 0) {
        this.fieldError.set(null);
        this.error.set(
          'We could not complete the operation because of a connection problem. Try again.',
        );
      } else {
        this.fieldError.set(null);
        this.error.set(
          'We could not set your password. Try again or contact the administrator if the problem continues.',
        );
      }
    }
  }
}