import { Injectable } from '@angular/core';

/**
 * Minimal opt-in interface sounds, generated with the Web Audio API — no
 * assets, no dependencies. Disabled by default and only ever enabled after
 * explicit user interaction (the pipeline "sound" toggle), so the product
 * works fully silent and never plays audio unprompted. All sounds are short,
 * low-gain pulses; the AudioContext is created lazily on first use.
 *
 * Reference notes: the concept follows Procedural-sounds / Cuelume (subtle,
 * purposeful interface audio), adapted to native Web Audio in Angular.
 */
@Injectable({ providedIn: 'root' })
export class Sound {
  private enabled = false;
  private ctx: AudioContext | null = null;

  setEnabled(on: boolean): void {
    this.enabled = on;
    if (!on) {
      // Free the context so silence is complete.
      this.ctx?.close().catch(() => undefined);
      this.ctx = null;
    }
  }

  isEnabled(): boolean {
    return this.enabled;
  }

  /** Short tick — stage advance (660 Hz). */
  tick(): void {
    const ctx = this.ctxOrNull();
    if (!ctx) return;
    this.pulse(ctx, 660, 0.045, 0.045);
  }

  /** Two-tone resolve — decision reached (523 → 784 Hz). */
  resolve(): void {
    const ctx = this.ctxOrNull();
    if (!ctx) return;
    this.pulse(ctx, 523, 0.045, 0.06);
    this.pulse(ctx, 784, 0.045, 0.09);
  }

  private ctxOrNull(): AudioContext | null {
    if (!this.enabled) return null;
    const Ctor =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext;
    if (!Ctor) return null;
    if (!this.ctx) this.ctx = new Ctor();
    if (this.ctx.state === 'suspended') void this.ctx.resume();
    return this.ctx;
  }

  private pulse(ctx: AudioContext, frequency: number, gain: number, at: number): void {
    const osc = ctx.createOscillator();
    const vol = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.value = frequency;
    vol.gain.setValueAtTime(0.0001, ctx.currentTime + at);
    vol.gain.exponentialRampToValueAtTime(gain, ctx.currentTime + at + 0.012);
    vol.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + at + 0.13);
    osc.connect(vol).connect(ctx.destination);
    osc.start(ctx.currentTime + at);
    osc.stop(ctx.currentTime + at + 0.16);
  }
}