import { TestBed } from '@angular/core/testing';
import { AiCost, computeAiCosts } from './ai-cost';

describe('computeAiCosts (pure calculator kernel)', () => {
  it('computes monthly invoices as perDay × days', () => {
    const res = computeAiCosts({
      invoicesPerDay: 20,
      operatingDays: 22,
      costPerInvoiceUsd: 0.05,
      reprocessPct: 0,
    });
    expect(res).not.toHaveProperty('error');
    const r = res as { monthlyInvoices: number };
    expect(r.monthlyInvoices).toBe(440);
  });

  it('computes the monthly, annual and adjusted per-invoice cost without reprocessing', () => {
    const res = computeAiCosts({
      invoicesPerDay: 10,
      operatingDays: 20,
      costPerInvoiceUsd: 0.05,
      reprocessPct: 0,
    }) as { monthlyCostUsd: number; annualCostUsd: number; adjustedCostPerInvoiceUsd: number };

    // monthlyInvoices = 200 → monthly = 200 × 0.05 = 10 USD
    expect(res.monthlyCostUsd).toBeCloseTo(10, 6);
    expect(res.annualCostUsd).toBeCloseTo(120, 6);
    expect(res.adjustedCostPerInvoiceUsd).toBeCloseTo(0.05, 6);
  });

  it('applies the reprocess percentage to all cost outputs', () => {
    const res = computeAiCosts({
      invoicesPerDay: 10,
      operatingDays: 20,
      costPerInvoiceUsd: 0.1,
      reprocessPct: 10,
    }) as {
      monthlyCostUsd: number;
      annualCostUsd: number;
      adjustedCostPerInvoiceUsd: number;
    };

    // monthlyInvoices = 200; adjusted = 0.1 × 1.10 = 0.11 → monthly = 200 × 0.11 = 22
    expect(res.monthlyCostUsd).toBeCloseTo(22, 6);
    expect(res.annualCostUsd).toBeCloseTo(264, 6);
    expect(res.adjustedCostPerInvoiceUsd).toBeCloseTo(0.11, 6);
  });

  it('handles decimal inputs (fractional invoices/day)', () => {
    const res = computeAiCosts({
      invoicesPerDay: 12.5,
      operatingDays: 21,
      costPerInvoiceUsd: 0.03,
      reprocessPct: 0,
    }) as { monthlyInvoices: number; monthlyCostUsd: number };

    expect(res.monthlyInvoices).toBeCloseTo(262.5, 6);
    expect(res.monthlyCostUsd).toBeCloseTo(7.875, 6);
  });

  it('returns zero for all-zero inputs', () => {
    const res = computeAiCosts({
      invoicesPerDay: 0,
      operatingDays: 0,
      costPerInvoiceUsd: 0,
      reprocessPct: 0,
    }) as { monthlyInvoices: number; monthlyCostUsd: number; annualCostUsd: number };

    expect(res.monthlyInvoices).toBe(0);
    expect(res.monthlyCostUsd).toBe(0);
    expect(res.annualCostUsd).toBe(0);
  });

  it('rejects negative inputs instead of returning misleading numbers', () => {
    const res = computeAiCosts({
      invoicesPerDay: -1,
      operatingDays: 22,
      costPerInvoiceUsd: 0.05,
      reprocessPct: 0,
    });
    expect(res).toHaveProperty('error');
  });

  it('rejects NaN and non-finite inputs', () => {
    const nan = computeAiCosts({
      invoicesPerDay: Number.NaN,
      operatingDays: 22,
      costPerInvoiceUsd: 0.05,
      reprocessPct: 0,
    });
    const inf = computeAiCosts({
      invoicesPerDay: 10,
      operatingDays: Number.POSITIVE_INFINITY,
      costPerInvoiceUsd: 0.05,
      reprocessPct: 0,
    });
    expect(nan).toHaveProperty('error');
    expect(inf).toHaveProperty('error');
  });

  it('does not accept negative reprocessing either', () => {
    const res = computeAiCosts({
      invoicesPerDay: 10,
      operatingDays: 20,
      costPerInvoiceUsd: 0.05,
      reprocessPct: -5,
    });
    expect(res).toHaveProperty('error');
  });
});

describe('AiCost component', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AiCost],
    }).compileComponents();
  });

  it('renders the section with the required title', () => {
    const fixture = TestBed.createComponent(AiCost);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('How much does it cost to automate your invoices?');
  });

  it('shows results by default with the illustrative assumption', () => {
    const fixture = TestBed.createComponent(AiCost);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    // default 20/day × 22 days = 440 monthly invoices
    expect(text).toContain('440');
    // default cost 0.05 × reprocess 5% → adjusted 0.0525
    expect(text).toContain('$0.05');
  });

  it('switches to an error banner when an input is negative', () => {
    const fixture = TestBed.createComponent(AiCost);
    fixture.detectChanges();

    const daily = fixture.nativeElement.querySelectorAll(
      '.ai-cost__controls input',
    )[0] as HTMLInputElement;
    daily.value = '-3';
    daily.dispatchEvent(new Event('input'));

    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('All values must be zero or a positive number.');
    expect(text).not.toContain('Estimated annual cost');
  });

  it('clears the error and recomputes after a valid correction', () => {
    const fixture = TestBed.createComponent(AiCost);
    fixture.detectChanges();

    const daily = fixture.nativeElement.querySelectorAll(
      '.ai-cost__controls input',
    )[0] as HTMLInputElement;
    daily.value = '-3';
    daily.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    daily.value = '10';
    daily.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Estimated monthly AI cost');
  });
});
