import { Component, computed, signal } from '@angular/core';
import { CurrencyPipe, DecimalPipe } from '@angular/common';

/**
 * Pure calculation kernel for the AI cost estimator. Exported for direct
 * testing: given valid numeric inputs it returns the estimated provider IA
 * cost; invalid inputs (NaN, negatives, non-finite) return an error object
 * instead of misleading numbers. These are *estimates* — never a quote and
 * never a total product cost.
 */
export interface AiCostInputs {
  invoicesPerDay: number;
  operatingDays: number;
  costPerInvoiceUsd: number;
  reprocessPct: number;
}

export interface AiCostResult {
  monthlyInvoices: number;
  monthlyCostUsd: number;
  annualCostUsd: number;
  adjustedCostPerInvoiceUsd: number;
}

export function computeAiCosts(
  inputs: AiCostInputs,
): AiCostResult | { error: string } {
  const values = [
    inputs.invoicesPerDay,
    inputs.operatingDays,
    inputs.costPerInvoiceUsd,
    inputs.reprocessPct,
  ];
  for (const v of values) {
    if (!Number.isFinite(v) || v < 0) {
      return { error: 'All values must be zero or a positive number.' };
    }
  }

  const monthlyInvoices = inputs.invoicesPerDay * inputs.operatingDays;
  const reprocessFactor = 1 + inputs.reprocessPct / 100;
  const monthlyCostUsd = monthlyInvoices * inputs.costPerInvoiceUsd * reprocessFactor;
  const annualCostUsd = monthlyCostUsd * 12;
  const adjustedCostPerInvoiceUsd = inputs.costPerInvoiceUsd * reprocessFactor;

  return {
    monthlyInvoices,
    monthlyCostUsd,
    annualCostUsd,
    adjustedCostPerInvoiceUsd,
  };
}

const DEFAULT_DAILY = '20';
const DEFAULT_DAYS = '22';
const DEFAULT_COST = '0.05'; // illustrative assumption, editable — not a real price
const DEFAULT_REPROCESS = '5';

/**
 * pb-ai-cost — landing section explaining and estimating the AI provider cost
 * of invoice extraction. Runs entirely in the browser: it never calls a
 * provider, never touches API keys, and never modifies policy or financial
 * logic. Results show the formulas used and clearly distinguish an estimated
 * scenario from measured real cost (none measured yet).
 */
@Component({
  selector: 'pb-ai-cost',
  imports: [DecimalPipe, CurrencyPipe],
  template: `
    <section class="ai-cost" aria-labelledby="ai-cost-title">
      <div class="ai-cost__head">
        <p class="split__folio">AI operating cost</p>
        <h2 id="ai-cost-title" class="fullhead__title">
          How much does it cost to automate your invoices?
        </h2>
        <p class="fullhead__note">
          The cost depends on the model used, the volume of documents and the
          token consumption. This calculator models an
          <strong>estimated AI provider cost scenario</strong> — it is not an
          official price and it does not represent the total product cost.
        </p>
      </div>

      <div class="ai-cost__grid">
        <div class="ai-cost__controls" aria-label="Cost estimator inputs">
          <label class="ai-field">
            <span class="ai-field__label">Invoices processed per day</span>
            <input
              type="number"
              min="0"
              step="1"
              inputmode="decimal"
              [value]="invoicesPerDay()"
              (input)="setDaily($event)"
            />
          </label>

          <label class="ai-field">
            <span class="ai-field__label">Operating days per month</span>
            <input
              type="number"
              min="0"
              step="1"
              inputmode="decimal"
              [value]="operatingDays()"
              (input)="setDays($event)"
            />
          </label>

          <label class="ai-field">
            <span class="ai-field__label">
              Estimated AI cost per invoice (USD)
            </span>
            <input
              type="number"
              min="0"
              step="0.001"
              inputmode="decimal"
              [value]="costPerInvoice()"
              (input)="setCost($event)"
            />
            <span class="ai-field__hint">
              Editable illustrative assumption — not a real provider price.
            </span>
          </label>

          <label class="ai-field">
            <span class="ai-field__label">
              Reprocessing percentage (optional)
            </span>
            <input
              type="number"
              min="0"
              step="1"
              inputmode="decimal"
              [value]="reprocessPct()"
              (input)="setReprocess($event)"
            />
            <span class="ai-field__hint">
              Invoices that need a second extraction.
            </span>
          </label>
        </div>

        <div class="ai-cost__results" [attr.aria-live]="'polite'">
          @if (result(); as res) {
            <dl class="ai-results">
              <div class="ai-results__row">
                <dt>Estimated monthly invoices</dt>
                <dd class="pb-mono">{{ res.monthlyInvoices | number }}</dd>
              </div>
              <div class="ai-results__row">
                <dt>Estimated monthly AI cost</dt>
                <dd class="pb-mono">{{ res.monthlyCostUsd | currency: 'USD' }}</dd>
              </div>
              <div class="ai-results__row">
                <dt>Estimated annual cost</dt>
                <dd class="pb-mono">{{ res.annualCostUsd | currency: 'USD' }}</dd>
              </div>
              <div class="ai-results__row">
                <dt>Estimated cost per invoice (with reprocessing)</dt>
                <dd class="pb-mono">{{ res.adjustedCostPerInvoiceUsd | currency: 'USD' }}</dd>
              </div>
            </dl>

            <div class="ai-formulas">
              <p class="ai-formulas__title">How it is calculated</p>
              <code class="ai-formulas__row">monthly_invoices = per_day × days</code>
              <code class="ai-formulas__row">monthly_cost = monthly_invoices × cost_per_invoice × (1 + %reprocess/100)</code>
              <code class="ai-formulas__row">annual_cost = monthly_cost × 12</code>
              <code class="ai-formulas__row">adjusted_per_invoice = cost_per_invoice × (1 + %reprocess/100)</code>
            </div>
          } @else if (error()) {
            <div class="ai-error" role="alert">
              <span class="ai-error__mark" aria-hidden="true">✕</span>
              <p>{{ error() }}</p>
            </div>
          }
        </div>
      </div>

      <div class="ai-cost__fineprint">
        <p>
          <strong>Illustrative assumption.</strong> There are no real measured
          costs in the project yet; adjust the per-invoice cost when you have
          usage data. This estimate covers only the AI provider cost for
          extraction and does not include infrastructure, storage, database,
          monitoring or other services. Different invoices may consume a
          different amount of tokens: the outcome is a scenario, not a
          measurement. No provider is called and no API keys are used from this
          section. The policy engine and financial evaluation logic are not
          modified here.
        </p>
      </div>
    </section>
  `,
  styles: `
    .ai-cost {
      background: linear-gradient(180deg, var(--pb-surface-2), transparent);
      border-radius: var(--pb-radius-l);
      padding: clamp(1.5rem, 4vw, 3rem);
    }

    .ai-cost__head {
      max-width: 720px;
    }

    .ai-cost__grid {
      display: grid;
      grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
      gap: 1.5rem;
      margin-top: 1.75rem;
    }

    .ai-cost__controls {
      display: grid;
      gap: 1rem;
      align-content: start;
    }

    .ai-field {
      display: grid;
      gap: 0.375rem;
    }

    .ai-field__label {
      font-weight: 600;
      font-size: var(--pb-text-sm);
      color: var(--pb-ink-soft);
    }

    .ai-field input {
      padding: 0.625rem 0.8125rem;
      border: 1px solid var(--pb-line-strong);
      border-radius: var(--pb-radius-m);
      background: var(--pb-surface);
      font-size: var(--pb-text-base);
      transition: border-color var(--pb-dur) var(--pb-ease);
    }

    .ai-field input:focus-visible {
      outline: 2px solid var(--pb-focus, var(--pb-accent-strong));
      outline-offset: 1px;
      border-color: transparent;
    }

    .ai-field__hint {
      font-size: var(--pb-text-xs);
      color: var(--pb-muted);
    }

    .ai-cost__results {
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius);
      background: var(--pb-surface);
      padding: 1.25rem;
      display: grid;
      gap: 1.25rem;
      align-content: start;
    }

    .ai-results {
      margin: 0;
      display: grid;
      gap: 0.5rem;
    }

    .ai-results__row {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 1rem;
      padding: 0.5rem 0;
      border-bottom: 1px solid var(--pb-line);
    }

    .ai-results__row:last-child {
      border-bottom: none;
    }

    .ai-results__row dt {
      color: var(--pb-ink-soft);
      font-size: var(--pb-text-sm);
    }

    .ai-results__row dd {
      margin: 0;
      font-weight: 600;
      font-size: 1.0625rem;
    }

    .ai-formulas {
      border-top: 1px dashed var(--pb-line-strong);
      padding-top: 1rem;
      display: grid;
      gap: 0.375rem;
    }

    .ai-formulas__title {
      margin: 0 0 0.25rem;
      font-size: var(--pb-text-xs);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--pb-muted);
    }

    .ai-formulas__row {
      display: block;
      font-family: var(--pb-font-mono);
      font-size: 0.8125rem;
      color: var(--pb-ink-soft);
    }

    .ai-error {
      display: flex;
      align-items: center;
      gap: 0.625rem;
      padding: 1rem;
      border: 1px solid var(--pb-blocked-bg);
      background: var(--pb-blocked-bg);
      border-radius: var(--pb-radius-m);
      color: var(--pb-blocked);
      font-size: var(--pb-text-sm);
    }

    .ai-error__mark {
      font-weight: 700;
    }

    .ai-error p {
      margin: 0;
    }

    .ai-cost__fineprint {
      margin-top: 1.5rem;
      font-size: var(--pb-text-xs);
      color: var(--pb-muted);
      max-width: 860px;
    }

    .ai-cost__fineprint p {
      margin: 0;
    }

    @media (max-width: 720px) {
      .ai-cost__grid {
        grid-template-columns: 1fr;
      }
    }
  `,
})
export class AiCost {
  protected readonly invoicesPerDay = signal(DEFAULT_DAILY);
  protected readonly operatingDays = signal(DEFAULT_DAYS);
  protected readonly costPerInvoice = signal(DEFAULT_COST);
  protected readonly reprocessPct = signal(DEFAULT_REPROCESS);

  protected readonly summary = computed<{
    result: AiCostResult | null;
    error: string | null;
  }>(() => {
    const daily = Number(this.invoicesPerDay());
    const days = Number(this.operatingDays());
    const cost = Number(this.costPerInvoice());
    const reprocess = Number(this.reprocessPct());

    const res = computeAiCosts({
      invoicesPerDay: daily,
      operatingDays: days,
      costPerInvoiceUsd: cost,
      reprocessPct: reprocess,
    });

    if ('error' in res) {
      return { result: null, error: res.error };
    }
    return { result: res, error: null };
  });

  /** Derived read-only projections of the summary (allows template narrowing). */
  protected readonly result = computed<AiCostResult | null>(() => this.summary().result);
  protected readonly error = computed<string | null>(() => this.summary().error);

  protected setDaily(event: Event): void {
    this.invoicesPerDay.set((event.target as HTMLInputElement).value);
  }

  protected setDays(event: Event): void {
    this.operatingDays.set((event.target as HTMLInputElement).value);
  }

  protected setCost(event: Event): void {
    this.costPerInvoice.set((event.target as HTMLInputElement).value);
  }

  protected setReprocess(event: Event): void {
    this.reprocessPct.set((event.target as HTMLInputElement).value);
  }
}
