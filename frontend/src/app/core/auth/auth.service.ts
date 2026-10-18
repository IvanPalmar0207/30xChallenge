import { computed, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AuthStatus,
  LoginResponse,
  MembershipSummary,
  RefreshResponse,
  UserProfile,
} from './models';

/**
 * Centralized JWT auth state.
 *
 * Security model (see the auth audit):
 * - The ACCESS token lives ONLY in memory (module signal): it is never
 *   persisted, so a page reload drops it and restore() re-derives it from
 *   the refresh token.
 * - The REFRESH token lives ONLY in an HttpOnly cookie set by the backend
 *   (path /api/v1/auth/); JavaScript never reads or writes it. All API
 *   calls use withCredentials so the browser can send/rotate that cookie.
 * - A stored token is never treated as "authorized": restore() always calls
 *   /auth/refresh/ and /auth/me/; Django validates permissions per request.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly accessToken = signal<string | null>(null);
  readonly user = signal<UserProfile | null>(null);
  readonly status = signal<AuthStatus>('restoring');
  readonly isAuthed = computed(() => this.status() === 'authed');
  private restorePromise: Promise<boolean> | null = null;

  /** Convenience: first membership, useful for the shell context. */
  readonly currentMembership = computed<MembershipSummary | null>(() => {
    const memberships = this.user()?.memberships ?? [];
    return memberships.length ? memberships[0] : null;
  });

  constructor(private readonly http: HttpClient) {}

  private api(path: string) {
    return `${environment.apiBaseUrl}${path}`;
  }

  async login(email: string, password: string): Promise<UserProfile> {
    try {
      const body = await firstValueFrom(
        this.http.post<LoginResponse>(this.api('/auth/login/'), { email, password }),
      );
      this.accessToken.set(body.access);
      // The login payload only carries identity; memberships come from /me/,
      // which is the source of truth for orgs and roles.
      const me = await firstValueFrom(
        this.http.get<UserProfile>(this.api('/auth/me/')),
      );
      this.user.set(me);
      this.status.set('authed');
      return me;
    } catch (error) {
      this.clear();
      throw error;
    }
  }

  /** Single-flight refresh used by the interceptor and restore(). */
  async refreshOnce(): Promise<boolean> {
    if (this.restorePromise) return this.restorePromise;
    this.restorePromise = this.doRefresh();
    try {
      return await this.restorePromise;
    } finally {
      this.restorePromise = null;
    }
  }

  private async doRefresh(): Promise<boolean> {
    try {
      const body = await firstValueFrom(
        this.http.post<RefreshResponse>(this.api('/auth/refresh/'), {}) /* withCredentials via interceptor */,
      );
      this.accessToken.set(body.access);
      return true;
    } catch {
      this.clear();
      return false;
    }
  }

  /** Restore after reload: refresh (cookie) -> me -> authed. */
  async restore(): Promise<boolean> {
    if (this.isAuthed()) return true;
    const ok = await this.refreshOnce();
    if (!ok) return false;
    try {
      const me = await firstValueFrom(
        this.http.get<UserProfile>(this.api('/auth/me/')),
      );
      this.user.set(me);
      this.status.set('authed');
      return true;
    } catch {
      this.clear();
      return false;
    }
  }

  async fetchMe(): Promise<void> {
    const me = await firstValueFrom(
      this.http.get<UserProfile>(this.api('/auth/me/')),
    );
    this.user.set(me);
  }

  async logout(): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(this.api('/auth/logout/'), {}, { responseType: 'text' }),
      );
    } finally {
      this.clear();
    }
  }

  /**
   * Set the initial password with a one-time setup token (public flow).
   * The raw token is never stored; the account cannot authenticate until
   * this succeeds. Returns void on success, throws on failure.
   */
  async setPassword(setupToken: string, password: string): Promise<void> {
    await firstValueFrom(
      this.http.post(this.api('/auth/set-password/'), {
        setup_token: setupToken,
        password,
      }),
    );
  }

  clear(): void {
    this.accessToken.set(null);
    this.user.set(null);
    this.status.set('guest');
  }
}