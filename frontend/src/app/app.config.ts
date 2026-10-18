import { provideAnimations } from '@angular/platform-browser/animations';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withViewTransitions } from '@angular/router';
import { routes } from './app.routes';
import { apiInterceptor } from './core/auth/auth.interceptor';

/**
 * View Transitions for route crossfades, @angular/animations for states, and
 * the HTTP stack with the JWT interceptor (Bearer + HttpOnly cookie).
 */
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withViewTransitions()),
    provideAnimations(),
    provideHttpClient(withInterceptors([apiInterceptor])),
  ],
};