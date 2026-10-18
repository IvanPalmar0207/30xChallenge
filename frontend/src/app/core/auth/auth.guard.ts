import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';

import { AuthService } from './auth.service';

/**
 * Guards /app. During initial restore (status 'restoring') it waits for the
 * refresh+me round-trip instead of redirecting prematurely. Guest users are
 * sent to /login preserving the intended destination. Django remains the
 * real authority for permissions; this only gates frontend navigation.
 */
export const authGuard: CanActivateFn = async (route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.status() === 'restoring') {
    await auth.restore();
  }
  if (auth.isAuthed()) {
    return true;
  }
  return router.createUrlTree(['/login'], { queryParams: { next: state.url } });
};