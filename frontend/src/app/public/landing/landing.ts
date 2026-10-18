import { Component, HostListener, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { CoverageMap } from './coverage-map';
import { HeroDemo } from './hero-demo';
import { InvoiceCycle } from './invoice-cycle';
import { InvoiceDemo } from './invoice-demo';
import { AiCost } from './ai-cost';
import { Logo } from '../../shared/logo';
import { Reveal } from '../../shared/reveal';

@Component({
  selector: 'pb-landing',
  imports: [
    RouterLink,
    Logo,
    Reveal,
    HeroDemo,
    InvoiceDemo,
    CoverageMap,
    InvoiceCycle,
    AiCost,
  ],
  templateUrl: './landing.html',
  styleUrl: './landing.scss',
})
export class Landing {
  protected readonly scrolled = signal(false);
  protected readonly menuOpen = signal(false);

  @HostListener('window:scroll')
  onScroll(): void {
    this.scrolled.set(window.scrollY > 8);
  }

  protected toggleMenu(): void {
    this.menuOpen.update((open) => !open);
  }

  protected closeMenu(): void {
    this.menuOpen.set(false);
  }
}