import { AfterViewInit, Directive, ElementRef, inject, OnDestroy } from '@angular/core';

/**
 * Scroll-reveal, fail-safe by construction:
 * - Content is VISIBLE by default. The hiding class is only added when an
 *   IntersectionObserver exists AND the user has not asked for reduced motion.
 * - The class is removed directly on the DOM element when the element enters
 *   the viewport, and by a safety timeout regardless of observer behaviour.
 * - If JS fails, the observer is missing, or reduced motion is preferred,
 *   the content is never hidden.
 */
@Directive({
  selector: '[pbReveal]',
})
export class Reveal implements AfterViewInit, OnDestroy {
  private readonly el = inject<ElementRef<HTMLElement>>(ElementRef);
  private observer?: IntersectionObserver;
  private timer = -1;

  ngAfterViewInit(): void {
    const el = this.el.nativeElement;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || typeof IntersectionObserver === 'undefined') {
      return; // visible by default
    }
    el.classList.add('pb-reveal-pending');
    this.observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            this.reveal();
            return;
          }
        }
      },
      { threshold: 0.1, rootMargin: '0px 0px -6% 0px' },
    );
    this.observer.observe(el);
    this.timer = window.setTimeout(() => this.reveal(), 1600);
  }

  private reveal(): void {
    this.el.nativeElement.classList.remove('pb-reveal-pending');
    this.observer?.disconnect();
    if (this.timer !== -1) {
      window.clearTimeout(this.timer);
      this.timer = -1;
    }
  }

  ngOnDestroy(): void {
    this.observer?.disconnect();
    window.clearTimeout(this.timer);
  }
}