import { Component, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { Icon } from '../../shared/icon';
import { Logo } from '../../shared/logo';
import { AuthService } from '../../core/auth/auth.service';

/**
 * Login screen — PayBlood identity: paper surface, ledger details.
 * Local validation (required fields), loading state, and a generic, safe
 * error message (never leaks server internals).
 */
@Component({
  selector: 'pb-login',
  imports: [FormsModule, RouterLink, Logo, Icon],
  template: `
    <main class="login">
      <section class="login__card" aria-labelledby="login-title">
        <a routerLink="/" class="login__brand" aria-label="Back to PayBlood home">
          <pb-logo />
        </a>

        <h1 id="login-title" class="login__title">Sign in to PayBlood</h1>
        <p class="login__lede">Access the invoice evaluation workspace.</p>

        <form
          #form="ngForm"
          class="login__form"
          (ngSubmit)="submit(form)"
          novalidate
        >
          <label class="field">
            <span class="field__label">Email</span>
            <input
              name="email"
              type="email"
              required
              autocomplete="username"
              placeholder="you@company.com"
              [(ngModel)]="email"
              #emailField="ngModel"
            />
          </label>

          <label class="field">
            <span class="field__label">Password</span>
            <input
              name="password"
              type="password"
              required
              autocomplete="current-password"
              placeholder="••••••••"
              [(ngModel)]="password"
              #passwordField="ngModel"
            />
          </label>

          <p class="login__error" role="alert" [attr.aria-live]="'polite'" [class.is-visible]="error()">
            {{ error() }}
          </p>

          <button
            type="submit"
            class="pb-btn pb-btn--primary login__submit"
            [disabled]="loading() || (!email().trim() || !password().trim())"
          >
            @if (loading()) {
              <pb-icon name="loader" [spin]="true" />
              Signing in…
            } @else {
              Sign in
            }
          </button>
        </form>

        <a routerLink="/" class="pb-btn pb-btn--ghost login__back">
          Back to home
        </a>

        <p class="login__note">
          Demo credentials are issued by an administrator via the invitation
          flow. Authentication is handled by the backend; no token is stored
          in browser storage.
        </p>
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
      max-width: 420px;
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

    .field input {
      padding: 0.625rem 0.8125rem;
      border: 1px solid var(--pb-line-strong);
      border-radius: var(--pb-radius-m);
      background: var(--pb-surface);
      font-size: var(--pb-text-base);
      transition: border-color var(--pb-dur) var(--pb-ease);
    }

    .field input:focus-visible {
      outline: 2px solid var(--pb-focus);
      outline-offset: 1px;
      border-color: transparent;
    }

    .login__error {
      min-height: 1.25rem;
      color: var(--pb-blocked);
      font-size: var(--pb-text-sm);
    }

    .login__error:not(.is-visible) {
      visibility: hidden;
    }

    .login__submit {
      width: 100%;
    }

    .login__back {
      width: 100%;
      margin-top: var(--pb-space-2);
      text-decoration: none;
    }

    .login__note {
      margin-top: var(--pb-space-4);
      color: var(--pb-muted);
      font-size: var(--pb-text-xs);
    }
  `,
})
export class LoginPage {
  protected readonly email = signal('');
  protected readonly password = signal('');
  protected readonly loading = signal(false);
  protected readonly error = signal('');

  constructor(
    private readonly auth: AuthService,
    private readonly router: Router,
    private readonly route: ActivatedRoute,
  ) {}

  protected async submit(form: NgForm): Promise<void> {
    if (this.loading() || form.invalid) return;
    this.loading.set(true);
    this.error.set('');
    try {
      const profile = await this.auth.login(this.email().trim(), this.password());
      const next = this.route.snapshot.queryParamMap.get('next');
      if (next && next.startsWith('/')) {
        await this.router.navigate([next]);
        return;
      }
      // Default landing:
      // - any member -> workspace dashboard (/app);
      // - a global superadmin without memberships -> Global administration;
      // - anyone else without memberships -> Organizations.
      const hasMemberships = (profile.memberships ?? []).length > 0;
      if (hasMemberships) {
        await this.router.navigate(['/app']);
      } else if (profile.is_global_admin) {
        await this.router.navigate(['/app/admin/organizations']);
      } else {
        await this.router.navigate(['/app/organizations']);
      }
    } catch {
      this.error.set('Invalid email or password. Please try again.');
    } finally {
      this.loading.set(false);
    }
  }
}