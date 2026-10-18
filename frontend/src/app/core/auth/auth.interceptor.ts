import {
  HttpErrorResponse,
  HttpInterceptorFn,
  HttpRequest,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, from, mergeMap, throwError } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';

const AUTH_SKIP = ['/auth/login/', '/auth/refresh/'];

/**
 * API interceptor.
 * - Attaches "Authorization: Bearer <access>" ONLY to PayBlood API requests.
 * - Sets withCredentials for API requests so the HttpOnly refresh cookie is
 *   sent and rotated (never read by JS).
 * - On 401 from the API (outside login/refresh): one controlled refresh with
 *   single-flight coordination; a failed refresh clears state and redirects
 *   to /login without an infinite loop. 403 is never treated as a session
 *   problem (Django's per-request permission check wins).
 */
export const apiInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const isApi = req.url.startsWith(environment.apiBaseUrl);
  if (!isApi) {
    return next(req); // never forward credentials to other hosts
  }

  if (AUTH_SKIP.some((suffix) => req.url.includes(suffix))) {
    return next(req.clone({ withCredentials: true }));
  }

  let outgoing: HttpRequest<unknown> = req.clone({ withCredentials: true });
  const token = auth.accessToken();
  if (token) {
    outgoing = outgoing.clone({
      headers: outgoing.headers.set('Authorization', `Bearer ${token}`),
    });
  }

  return next(outgoing).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status !== 401) {
        return throwError(() => error);
      }
      // 401 on the API: try one controlled refresh.
      return from(auth.refreshOnce()).pipe(
        mergeMap((refreshed) => {
          if (!refreshed) {
            router.navigate(['/login']);
            return throwError(() => error);
          }
          const retry = req.clone({
            withCredentials: true,
            setHeaders: {
              Authorization: `Bearer ${auth.accessToken() ?? ''}`,
            },
          });
          return next(retry);
        }),
      );
    }),
  );
};