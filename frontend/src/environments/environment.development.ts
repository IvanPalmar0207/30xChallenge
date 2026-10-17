/**
 * Development overrides for public build-time configuration (see
 * environment.ts for security notes — values here are public too).
 */
export const environment = {
  production: false,
  /** DRF API base URL served by `manage.py runserver`. */
  apiBaseUrl: "http://localhost:8000/api/v1",
};
