/**
 * Public build-time configuration for PayBlood.
 *
 * SECURITY: everything in this file is bundled and shipped to the browser, so
 * it must be treated as public. Never place credentials, API keys, or secrets
 * in frontend code. Backend secrets live only in the gitignored `.env`.
 *
 * `environment.ts` holds the default (production build) values; the
 * development build swaps in `environment.development.ts` via
 * `angular.json` -> `build.configurations.development.fileReplacements`.
 */
export const environment = {
  production: true,
  /** DRF API base URL for the deployed environment; set per deployment. */
  apiBaseUrl: "https://payblood-production.up.railway.app/api/v1",
};
