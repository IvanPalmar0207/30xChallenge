/**
 * Unit tests for extraction page component (Slice 7).
 * Verifies file selection, extraction, review, vendor loading, and invoice
 * creation against the real API contracts used by the page.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { signal } from '@angular/core';

import { ExtractionPage } from './extraction';
import { AuthService } from '../../core/auth/auth.service';
import { ExtractionService } from './extraction.service';
import { InvoicesService } from '../invoices/invoices.service';
import { environment } from '../../../environments/environment';
import { ExtractedField, ExtractionResult, VendorSummary } from './extraction.models';

describe('ExtractionPage', () => {
  let component: ExtractionPage;
  let fixture: ComponentFixture<ExtractionPage>;
  let httpMock: HttpTestingController;

  const fakeMembership = {
    organization_id: 'org-123',
    organization_name: 'Test Org',
    role: 'FINANCE_ADMIN' as const,
  };

  const fakeUser = {
    id: 'user-1',
    username: 'testuser',
    email: 'test@example.com',
    first_name: 'Test',
    last_name: 'User',
    memberships: [fakeMembership],
  };

  function field(
    value: string | null,
    evidence: string | null = null,
    confidence: ExtractedField['confidence'] = 'absent',
    validation_errors: string[] = [],
  ): ExtractedField {
    return { value, evidence, confidence, validation_errors };
  }

  function makeFields(
    overrides: Record<string, Partial<ExtractedField>> = {},
  ): Record<string, ExtractedField> {
    const base: Record<string, ExtractedField> = {
      vendor_name: field(null),
      vendor_tax_id: field(null),
      invoice_number: field(null),
      issue_date: field(null),
      due_date: field(null),
      currency: field(null),
      amount: field(null),
      description: field(null),
    };
    for (const [name, override] of Object.entries(overrides)) {
      base[name] = { ...base[name], ...override } as ExtractedField;
    }
    return base;
  }

  function makeResult(
    overrides: Partial<ExtractionResult> & {
      fields?: Record<string, Partial<ExtractedField>>;
    } = {},
  ): ExtractionResult {
    const { fields: fieldOverrides, ...rest } = overrides;
    return {
      extraction_id: 'ext-1',
      provider_used: 'mock',
      model_used: 'mock-v1',
      verification_status: 'not_configured',
      verification_message: 'Verification provider not configured.',
      raw_text_extracted: false,
      fields: makeFields(fieldOverrides),
      cross_field_errors: [],
      warnings: [],
      ...rest,
    };
  }

  function vendor(
    id: string,
    legal_name: string,
    tax_id: string | null,
    status: VendorSummary['status'] = 'active',
  ): VendorSummary {
    return { id, legal_name, tax_id, status };
  }

  beforeEach(async () => {
    const authMock: any = {
      currentMembership: signal(fakeMembership),
      user: signal(fakeUser),
    };

    await TestBed.configureTestingModule({
      imports: [ExtractionPage, HttpClientTestingModule],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authMock },
        ExtractionService,
        InvoicesService,
      ],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ExtractionPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('initializes in idle state', () => {
    expect(component.state()).toBe('idle');
    expect(component.selectedFile()).toBeNull();
    expect(component.extraction()).toBeNull();
  });

  it('rejects unsupported file types and clears stale selection', () => {
    component.selectedFile.set(new File([], 'old.pdf'));
    const file = new File(['content'], 'report.docx', { type: 'application/msword' });

    component.onFileSelected({ target: { files: [file], value: 'chosen' } } as any);

    expect(component.clientError()).toContain('Unsupported file type');
    expect(component.state()).toBe('idle');
    expect(component.selectedFile()).toBeNull();
  });

  it('rejects oversized files', () => {
    const largeContent = new Uint8Array(11 * 1024 * 1024); // 11 MB
    const file = new File([largeContent], 'large.pdf', { type: 'application/pdf' });

    component.onFileSelected({ target: { files: [file], value: 'chosen' } } as any);

    expect(component.clientError()).toContain('File too large');
    expect(component.state()).toBe('idle');
    expect(component.selectedFile()).toBeNull();
  });

  it('accepts valid JPEG files and clears the native input value', () => {
    const jpegContent = new Uint8Array([0xff, 0xd8, 0xff, 0xe0]).buffer;
    const file = new File([jpegContent], 'invoice.jpg', { type: 'image/jpeg' });
    const target = { files: [file], value: 'invoice.jpg' } as any;

    component.onFileSelected({ target } as any);

    expect(target.value).toBe('');
    expect(component.state()).toBe('selected');
    expect(component.selectedFile()).toBe(file);
    expect(component.selectedFileType()).toBe('JPEG');
  });

  it('accepts valid PDF files and creates a preview URL', () => {
    const pdfContent = new Uint8Array([0x25, 0x50, 0x44, 0x46]).buffer; // %PDF
    const file = new File([pdfContent], 'invoice.pdf', { type: 'application/pdf' });

    component.onFileSelected({ target: { files: [file], value: 'invoice.pdf' } } as any);

    expect(component.state()).toBe('selected');
    expect(component.selectedFile()).toBe(file);
    expect(component.selectedFileType()).toBe('PDF');
    expect(component.previewUrl()).toContain('blob:');
  });

  it('clears the selected file input when reset is called', () => {
    const file = new File(['content'], 'invoice.pdf', { type: 'application/pdf' });
    const input = { value: 'invoice.pdf', files: [file] } as any;
    component.fileInputRef = { nativeElement: input } as any;
    component.state.set('review');
    component.selectedFile.set(file);
    component.extraction.set(makeResult());

    component.reset();

    expect(component.state()).toBe('idle');
    expect(component.selectedFile()).toBeNull();
    expect(component.extraction()).toBeNull();
    expect(input.value).toBe('');
  });

  it('POSTs the file as multipart form data and enters review state', () => {
    const pdfContent = new Uint8Array([0x25, 0x50, 0x44, 0x46]).buffer;
    const file = new File([pdfContent], 'inv.pdf', { type: 'application/pdf' });
    component.selectedFile.set(file);
    component.state.set('selected');

    component.extract();
    expect(component.state()).toBe('processing');

    const req = httpMock.expectOne(
      `${environment.apiBaseUrl}/organizations/org-123/extraction/`,
    );
    expect(req.request.method).toBe('POST');
    expect((req.request.body as FormData).get('file')).toBe(file);

    req.flush(
      makeResult({
        fields: {
          vendor_name: field('Acme Corp', 'Acme Corp', 'medium'),
          vendor_tax_id: field('ACME-1', 'Tax ID: ACME-1', 'medium'),
          invoice_number: field('INV-100', 'Invoice: INV-100', 'medium'),
          issue_date: field('2026-10-01', '2026-10-01', 'medium'),
          due_date: field('2026-11-01', '2026-11-01', 'medium'),
          amount: field('100.00', '$100.00', 'medium'),
          currency: field('USD', 'USD', 'medium'),
        },
      }),
    );

    const vendorReq = httpMock.expectOne(
      `${environment.apiBaseUrl}/organizations/org-123/vendors/`,
    );
    vendorReq.flush([
      vendor('v-active', 'Acme Corp', 'ACME-1', 'active'),
      vendor('v-inactive', 'Legacy Corp', 'LEG-9', 'inactive'),
    ]);

    expect(component.state()).toBe('review');
    expect(component.form.value.invoice_number).toBe('INV-100');
    expect(component.form.value.vendor).toBe('v-active');
    expect(component.vendors().length).toBe(1);
    expect(component.vendors()[0].legal_name).toBe('Acme Corp');
  });

  it('filters inactive vendors and matches by legal name when tax id is missing', () => {
    component.extraction.set(
      makeResult({
        fields: {
          vendor_name: field('Acme Corp', 'Acme Corp', 'medium'),
          vendor_tax_id: field(null),
        },
      }),
    );

    component['loadVendors']('org-123');

    const vendorReq = httpMock.expectOne(
      `${environment.apiBaseUrl}/organizations/org-123/vendors/`,
    );
    vendorReq.flush([
      vendor('v-active', 'Acme Corp', 'ACME-1', 'active'),
      vendor('v-inactive', 'Legacy Corp', 'LEG-9', 'inactive'),
    ]);

    expect(component.vendors().length).toBe(1);
    expect(component.vendors()[0].status).toBe('active');
    expect(component.form.value.vendor).toBe('v-active');
  });

  it('does not issue duplicate extraction requests while not in selected state', () => {
    const file = new File(['content'], 'invoice.pdf', { type: 'application/pdf' });
    component.selectedFile.set(file);
    component.state.set('processing');

    component.extract();

    httpMock.expectNone(`${environment.apiBaseUrl}/organizations/org-123/extraction/`);
    expect(component.clientError()).toBe('');
    expect(component.state()).toBe('processing');
  });

  it('submits the reviewed invoice and shows the created invoice id on success', () => {
    component.state.set('review');
    component.form.patchValue({
      vendor: 'v-active',
      invoice_number: 'INV-100',
      issue_date: '2026-10-01',
      due_date: '2026-11-01',
      amount: '100.00',
      currency: 'usd',
      description: 'Consulting services',
    });

    component.submitReview();

    const req = httpMock.expectOne(
      `${environment.apiBaseUrl}/organizations/org-123/invoices/`,
    );
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      vendor: 'v-active',
      invoice_number: 'INV-100',
      issue_date: '2026-10-01',
      due_date: '2026-11-01',
      amount: '100.00',
      currency: 'USD',
      description: 'Consulting services',
    });

    req.flush({
      id: 'inv-created-1',
      vendor: { id: 'v-active', legal_name: 'Acme Corp', tax_id: 'ACME-1' },
      invoice_number: 'INV-100',
      issue_date: '2026-10-01',
      due_date: '2026-11-01',
      amount: '100.00',
      currency: 'USD',
      description: 'Consulting services',
      status: 'received',
      created_at: '2026-10-17T00:00:00Z',
      updated_at: '2026-10-17T00:00:00Z',
    });

    expect(component.state()).toBe('done');
    expect(component.createdInvoiceId()).toBe('inv-created-1');
  });

  it('keeps the review state and surfaces backend field errors when creation fails', () => {
    component.state.set('review');
    component.form.patchValue({
      vendor: 'v-active',
      invoice_number: 'INV-100',
      issue_date: '2026-10-01',
      due_date: '2026-11-01',
      amount: '100.00',
      currency: 'USD',
      description: 'Consulting services',
    });

    component.submitReview();

    const req = httpMock.expectOne(
      `${environment.apiBaseUrl}/organizations/org-123/invoices/`,
    );
    req.flush(
      { vendor: ['This vendor is inactive.'] },
      { status: 400, statusText: 'Bad Request' },
    );

    expect(component.state()).toBe('review');
    expect(component.serverError()).toContain('vendor');
    expect(component.serverError()).toContain('inactive');
  });
});
