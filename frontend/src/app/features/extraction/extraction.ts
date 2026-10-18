/**
 * Invoice extraction page component (Slice 7).
 * Drag-drop file upload, AI extraction, human review form, invoice creation.
 * Standalone component using Angular 22 signals and reactive forms.
 */
import {
  Component,
  computed,
  inject,
  OnDestroy,
  signal,
  ViewChild,
  ElementRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  FormBuilder,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { Router, RouterLink } from '@angular/router';
import { DomSanitizer } from '@angular/platform-browser';

import { Folio } from '../../shared/folio';
import { AuthService } from '../../core/auth/auth.service';
import { InvoicesService } from '../invoices/invoices.service';
import { ExtractionService } from './extraction.service';
import {
  ExtractionResult,
  InvoiceCreatePayload,
  VendorSummary,
} from './extraction.models';

type UploadState = 'idle' | 'selected' | 'processing' | 'review' | 'submitting' | 'done' | 'error';

@Component({
  selector: 'pb-extraction',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, Folio],
  templateUrl: './extraction.html',
  styleUrl: './extraction.scss',
})
export class ExtractionPage implements OnDestroy {
  private auth = inject(AuthService);
  private extractionService = inject(ExtractionService);
  private invoicesService = inject(InvoicesService);
  private router = inject(Router);
  protected readonly sanitizer = inject(DomSanitizer);
  private fb = inject(FormBuilder);

  // ── State signals ──
  state = signal<UploadState>('idle');
  selectedFile = signal<File | null>(null);
  dragOver = signal(false);
  extraction = signal<ExtractionResult | null>(null);
  vendors = signal<VendorSummary[]>([]);
  vendorsLoading = signal(false);
  clientError = signal<string>('');
  serverError = signal<string>('');
  createdInvoiceId = signal<string>('');
  previewUrl = signal<string>('');

  @ViewChild('fileInput') fileInputRef?: ElementRef<HTMLInputElement>;

  // ── Form ──
  form: FormGroup;

  // ── Computed ──
  currentMembership = this.auth.currentMembership;
  acceptedExtensions = computed(() => ['.pdf', '.jpg', '.jpeg', '.png']);
  formattedSize = computed(() => {
    const file = this.selectedFile();
    if (!file) return '';
    const mb = file.size / (1024 * 1024);
    return mb < 1 ? `${(file.size / 1024).toFixed(0)} KB` : `${mb.toFixed(1)} MB`;
  });
  selectedFileType = computed(() => {
    const file = this.selectedFile();
    if (!file) return '';
    const ext = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    if (ext === '.pdf') return 'PDF';
    if (ext === '.png') return 'PNG';
    if (ext === '.jpg' || ext === '.jpeg') return 'JPEG';
    return file.type || 'File';
  });

  // Reason the extract button is disabled (null when enabled)
  extractDisabledReason = computed<string | null>(() => {
    if (!this.selectedFile()) return 'Select a file to extract.';
    if (this.clientError()) return this.clientError();
    if (!this.currentMembership()) return 'No active organization. Sign in or select an organization.';
    return null;
  });

  canExtract() {
    return this.extractDisabledReason() === null;
  }

  constructor() {
    this.form = this.fb.group({
      invoice_number: ['', [Validators.required]],
      vendor: ['', [Validators.required]],
      issue_date: ['', [Validators.required]],
      due_date: [''],
      amount: ['', [Validators.required]],
      currency: ['USD', [Validators.required]],
      description: [''],
    });
  }

  // ── File handling ──
  onFileSelected(event?: Event | null): void {
    // Support direct invocation or native file input change events.
    let file: File | undefined | null = null;
    if (event) {
      const input = event.target as HTMLInputElement;
      file = input.files?.[0] ?? null;
      input.value = '';
    } else if (this.fileInputRef) {
      file = this.fileInputRef.nativeElement.files?.[0] ?? null;
    }
    if (file) {
      this.processFile(file);
    }
  }

  openFileDialog(): void {
    // Robustly open the hidden file input if available. Try ViewChild first,
    // then fallback to document lookup by id. This covers template scoping
    // edge cases where ViewChild is not yet set.
    try {
      if (this.fileInputRef && this.fileInputRef.nativeElement) {
        this.fileInputRef.nativeElement.click();
        return;
      }
      const el = document.getElementById('pb_file_input') as HTMLInputElement | null;
      if (el) {
        el.click();
        return;
      }
      // If neither exists, surface a clear error to the user.
      this.clientError.set('File input unavailable. Try reloading the page.');
    } catch {
      // Never throw to the UI; show a friendly message.
      this.clientError.set('Unable to open file picker. Try with a different browser.');
    }
  }

  /**
   * The "Select file" label activates the hidden input natively via its
   * `for` attribute. Stop the click from bubbling to the drop zone, which
   * would call openFileDialog() a second time and cancel the picker.
   */
  stopFileDialog(event: Event): void {
    event.stopPropagation();
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(true);
  }

  onDragLeave(): void {
    this.dragOver.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) this.processFile(file);
  }

  private processFile(file: File): void {
    // Clear previous state so stale results never survive a new selection.
    this.clientError.set('');
    this.serverError.set('');
    this.selectedFile.set(null);
    this.extraction.set(null);
    this.vendors.set([]);
    this.vendorsLoading.set(false);
    this.createdInvoiceId.set('');
    this.form.reset({ currency: 'USD' });
    this.revokePreview();
    this.state.set('idle');

    // Validate extension
    const ext = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    if (!this.acceptedExtensions().includes(ext)) {
      this.clientError.set(`Unsupported file type: ${ext}. Accepted: PDF, JPEG, PNG.`);
      return;
    }

    // Validate size (10 MB limit, enforced by backend too)
    const maxMB = 10;
    if (file.size > maxMB * 1024 * 1024) {
      this.clientError.set(`File too large: ${this.formattedSize()}. Max: ${maxMB} MB.`);
      return;
    }

    this.selectedFile.set(file);

    // Generate preview URL for images
    if (ext === '.pdf') {
      const blob = new Blob([file], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      this.previewUrl.set(url);
    } else if (['.jpg', '.jpeg', '.png'].includes(ext)) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const dataUrl = e.target?.result as string;
        this.previewUrl.set(dataUrl);
      };
      reader.readAsDataURL(file);
    }

    this.state.set('selected');
  }

  // ── Extraction ──
  extract(): void {
    const file = this.selectedFile();
    const orgId = this.currentMembership()?.organization_id;

    if (this.state() !== 'selected' || !file || !orgId) {
      return;
    }

    this.state.set('processing');
    this.clientError.set('');
    this.serverError.set('');

    this.extractionService.extract(orgId, file).subscribe({
      next: (result) => {
        this.extraction.set(result);
        this.populateForm(result);
        this.loadVendors(orgId);
        this.state.set('review');
      },
      error: (err: HttpErrorResponse) => {
        this.serverError.set(this.errorMessage(err));
        this.state.set('error');
      },
    });
  }

  private populateForm(result: ExtractionResult): void {
    const fields = result.fields;
    this.form.patchValue({
      invoice_number: fields['invoice_number']?.value || '',
      issue_date: fields['issue_date']?.value || '',
      due_date: fields['due_date']?.value || '',
      amount: fields['amount']?.value || '',
      currency: fields['currency']?.value?.toUpperCase() || 'USD',
      description: fields['description']?.value || '',
    });
  }

  private loadVendors(orgId: string): void {
    this.vendorsLoading.set(true);
    this.extractionService.listVendors(orgId).subscribe({
      next: (vendors) => {
        const activeVendors = vendors.filter((vendor) => vendor.status === 'active');
        this.vendors.set(activeVendors);
        this.autoSelectVendor(activeVendors);
        this.vendorsLoading.set(false);
        if (activeVendors.length === 0) {
          this.serverError.set('No active vendors are available for this organization.');
        }
      },
      error: (err: HttpErrorResponse) => {
        this.vendors.set([]);
        this.vendorsLoading.set(false);
        this.serverError.set(
          this.errorMessage(err) || 'Unable to load vendors for this organization.'
        );
      },
    });
  }

  private autoSelectVendor(vendors: VendorSummary[]): void {
    const extraction = this.extraction();
    if (!extraction) return;

    const extractedTaxId = extraction.fields['vendor_tax_id']?.value;
    const extractedName = extraction.fields['vendor_name']?.value;

    const match =
      (extractedTaxId && vendors.find((v) => v.tax_id === extractedTaxId)) ||
      (extractedName &&
        vendors.find(
          (v) => v.legal_name.trim().toLowerCase() === extractedName.trim().toLowerCase(),
        ));

    if (match) {
      this.form.patchValue({ vendor: match.id });
    }
  }

  // ── Review form submission ──
  submitReview(): void {
    if (this.form.invalid || this.state() === 'submitting') {
      this.clientError.set('Please fill in all required fields.');
      return;
    }

    const orgId = this.currentMembership()?.organization_id;
    if (!orgId) {
      this.clientError.set('Missing organization context.');
      return;
    }

    this.state.set('submitting');
    this.serverError.set('');

    const payload: InvoiceCreatePayload = {
      vendor: this.form.value.vendor,
      invoice_number: this.form.value.invoice_number,
      issue_date: this.form.value.issue_date,
      due_date: this.form.value.due_date || null,
      amount: this.form.value.amount,
      currency: this.form.value.currency.toUpperCase(),
      description: this.form.value.description || null,
    };

    this.invoicesService.create(orgId, payload).subscribe({
      next: (invoice) => {
        this.createdInvoiceId.set(invoice.id);
        this.state.set('done');
      },
      error: (err: HttpErrorResponse) => {
        this.serverError.set(this.errorMessage(err));
        this.state.set('review');
      },
    });
  }

  // ── Reset ──
  reset(): void {
    this.state.set('idle');
    this.selectedFile.set(null);
    this.extraction.set(null);
    this.vendors.set([]);
    this.vendorsLoading.set(false);
    this.clientError.set('');
    this.serverError.set('');
    this.createdInvoiceId.set('');
    this.form.reset({ currency: 'USD' });
    this.revokePreview();
    if (this.fileInputRef?.nativeElement) {
      this.fileInputRef.nativeElement.value = '';
    }
  }

  // ── Helpers ──
  fieldConf(fieldName: string): string {
    const field = this.extraction()?.fields[fieldName];
    return field?.confidence || 'absent';
  }

  fieldErrors(fieldName: string): string[] {
    const field = this.extraction()?.fields[fieldName];
    return field?.validation_errors || [];
  }

  private errorMessage(err: HttpErrorResponse): string {
    const body = err.error;
    if (typeof body === 'string' && body.trim()) {
      return body;
    }
    if (body && typeof body === 'object') {
      for (const key of ['message', 'detail', 'error']) {
        const value = (body as Record<string, unknown>)[key];
        if (typeof value === 'string' && value.trim()) {
          return value;
        }
      }
      const fieldMessages = Object.entries(body as Record<string, unknown>)
        .filter(([key]) => !['message', 'detail', 'error'].includes(key))
        .flatMap(([key, value]) => this.flattenErrorMessages(value).map((message) => `${key}: ${message}`));
      if (fieldMessages.length) {
        return fieldMessages.join(' · ');
      }
    }
    if (err.status === 503) return 'AI extraction service unavailable. Please try again later.';
    if (err.status === 400) return 'Invalid file. Ensure it is a valid PDF, JPEG, or PNG.';
    if (err.status === 409) return 'This invoice already exists or was already decided.';
    return 'An error occurred. Please try again.';
  }

  private flattenErrorMessages(value: unknown): string[] {
    if (typeof value === 'string') {
      return [value];
    }
    if (Array.isArray(value)) {
      return value.flatMap((entry) => this.flattenErrorMessages(entry));
    }
    if (value && typeof value === 'object') {
      return Object.values(value as Record<string, unknown>).flatMap((entry) => this.flattenErrorMessages(entry));
    }
    return [];
  }

  private revokePreview(): void {
    const url = this.previewUrl();
    if (url && url.startsWith('blob:')) {
      URL.revokeObjectURL(url);
    }
    this.previewUrl.set('');
  }

  ngOnDestroy(): void {
    this.revokePreview();
  }
}
