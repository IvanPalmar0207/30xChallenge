import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  signal,
  viewChild,
} from '@angular/core';
import type * as L from 'leaflet';

import { Icon } from '../../shared/icon';
import { Region } from './types';

/**
 * Coverage map — real world map (Leaflet) with clean, bank-style light tiles
 * (CARTO "light_all", attribution kept). The 12 currencies PayBlood actually
 * accepts are pinned to their main market; each point opens the lateral
 * detail panel. No external data integrations exist — the panel states that
 * honestly instead of inventing providers.
 *
 * Leaflet is vanilla JS (no Angular peer) and mounts inside the component;
 * the map is destroyed on teardown to avoid route-change leaks.
 */

const REGIONS: Region[] = [
  { iso: 'US', country: 'United States', currency: 'USD', supported: true, use: 'Invoice currency validation', source: 'None today', lat: 39, lng: -98 },
  { iso: 'CA', country: 'Canada', currency: 'CAD', supported: true, use: 'Invoice currency validation', source: 'None today', lat: 56, lng: -106 },
  { iso: 'MX', country: 'Mexico', currency: 'MXN', supported: true, use: 'Invoice currency validation', source: 'None today', lat: 23, lng: -102 },
  { iso: 'CO', country: 'Colombia', currency: 'COP', supported: true, use: 'Invoice currency validation', source: 'None today', lat: 4, lng: -74 },
  { iso: 'BR', country: 'Brazil', currency: 'BRL', supported: true, use: 'Invoice currency validation', source: 'None today', lat: -10, lng: -51 },
  { iso: 'AR', country: 'Argentina', currency: 'ARS', supported: true, use: 'Invoice currency validation', source: 'None today', lat: -34, lng: -64 },
  { iso: 'PE', country: 'Peru', currency: 'PEN', supported: true, use: 'Invoice currency validation', source: 'None today', lat: -9, lng: -76 },
  { iso: 'CL', country: 'Chile', currency: 'CLP', supported: true, use: 'Invoice currency validation', source: 'None today', lat: -33, lng: -71 },
  { iso: 'GB', country: 'United Kingdom', currency: 'GBP', supported: true, use: 'Invoice currency validation', source: 'None today', lat: 54, lng: -2 },
  { iso: 'EU', country: 'Euro area', currency: 'EUR', supported: true, use: 'Invoice currency validation', source: 'None today', lat: 51, lng: 10 },
  { iso: 'CH', country: 'Switzerland', currency: 'CHF', supported: true, use: 'Invoice currency validation', source: 'None today', lat: 47, lng: 8 },
  { iso: 'JP', country: 'Japan', currency: 'JPY', supported: true, use: 'Invoice currency validation', source: 'None today', lat: 36, lng: 138 },
];

const HUB: [number, number] = [14, 25];

// Light world tiles without API key (bank-style look). If the primary
// provider fails, we fall back to OpenStreetMap automatically.
const TILE_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}';
const TILE_ATTR = 'Source: Esri, Maxar, Earthstar Geographics &copy; Esri';
const TILE_FALLBACK_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const TILE_FALLBACK_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

@Component({
  selector: 'pb-coverage-map',
  imports: [Icon],
  template: `
    <section class="map" aria-label="Coverage map — supported currencies">
      <div
        class="map__canvas"
        #mapEl
        tabindex="0"
        role="application"
        (keydown)="onMapKey($event)"
        aria-label="World map of supported currencies"
      ></div>

      <div class="map__panel" [attr.aria-live]="'polite'">
          @if (selected(); as region) {
            <div class="region">
              <header class="region__head">
                <img
                  class="region__flag"
                  [src]="flagUrl(region.iso)"
                  [alt]="'Flag of ' + region.country"
                  (error)="onFlagError($event)"
                  loading="lazy"
                />
                <div class="region__title">
                  <h3 class="region__country">{{ region.country }}</h3>
                  <p class="region__codes pb-mono">{{ region.iso }} · {{ region.currency }}</p>
                </div>
                <span class="region__status">
                  <pb-icon name="check" /> supported
                </span>
                <button
                  type="button"
                  class="region__close"
                  (click)="clear()"
                  aria-label="Close region detail"
                >
                  <pb-icon name="close" />
                </button>
              </header>

              <dl class="region__list">
                <div>
                  <dt>Used for</dt>
                  <dd>{{ region.use }}</dd>
                </div>
                <div>
                  <dt>External source</dt>
                  <dd>
                    <strong>{{ region.source }}</strong>
                    <span class="region__note">Banking and data integrations are a future phase — not invented here.</span>
                  </dd>
                </div>
                @if (region.detail; as detail) {
                  <div>
                    <dt>Detail</dt>
                    <dd>{{ detail }}</dd>
                  </div>
                }
              </dl>
            </div>
          } @else {
            <div class="region region--empty">
              <h3 class="region__country">No region selected</h3>
              <p class="region__hint">
                Select a point on the map (Tab + Enter works) to see what
                PayBlood really accepts for that market — and what it does not
                touch yet.
              </p>
            </div>
          }
        </div>
    </section>
  `,
  styles: `
    .map {
      display: grid;
      grid-template-columns: 1fr;
      gap: var(--pb-space-4);
    }

    .map__canvas {
      min-width: 0;
      height: 460px;
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-l);
      overflow: hidden;
      background: #eef0e6;
    }

    .map__canvas :global(.leaflet-container) {
      width: 100%;
      height: 100%;
    }

    .map__canvas :global(.leaflet-container) {
      background: #eef0e6;
      font-family: var(--pb-font-body);
    }

    .map__canvas :global(.leaflet-control-zoom) {
      border: 1px solid #d4d8c8 !important;
      border-radius: var(--pb-radius-s);
      box-shadow: none;
      overflow: hidden;
    }

    .map__canvas :global(.leaflet-control-zoom a) {
      color: #4a5340;
      border-bottom: 1px solid #e4e6d8;
      background: #fffdf7;
      width: 26px;
      height: 26px;
      line-height: 26px;
    }

    .map__canvas :global(.leaflet-tooltip.pb-tooltip) {
      background: #fffdf7;
      border: 1px solid #d4d8c8;
      border-radius: 4px;
      box-shadow: none;
      font-family: var(--pb-font-mono);
      font-size: 11px;
      color: #1a1f13;
      padding: 2px 8px;
    }

    .map__canvas :global(.leaflet-control-attribution) {
      font-size: 9px;
      background: rgb(255 253 247 / 0.85);
      color: #71795f;
    }

    .map__panel {
      min-width: 0;
    }

    .region {
      position: relative;
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-l);
      background: var(--pb-surface);
      padding: var(--pb-space-4) var(--pb-space-5);
      display: grid;
      gap: var(--pb-space-3);
      box-shadow: var(--pb-shadow-hairline);
    }

    .region__head {
      display: flex;
      align-items: center;
      gap: var(--pb-space-3);
      flex-wrap: wrap;
    }

    .region__flag {
      width: 40px;
      height: 27px;
      object-fit: cover;
      border-radius: var(--pb-radius-s);
      border: 1px solid var(--pb-line);
      background: var(--pb-surface-2);
    }

    .region__status {
      margin-left: auto;
    }

    .region__title {
      min-width: 0;
      flex: 1;
    }

    .region__country {
      font-size: 1.25rem;
      letter-spacing: -0.02em;
      overflow-wrap: anywhere;
    }

    .region__codes {
      margin-top: 0.125rem;
      color: var(--pb-muted);
      font-size: 0.8125rem;
    }

    .region__close {
      background: none;
      border: 1px solid var(--pb-line);
      border-radius: var(--pb-radius-m);
      color: var(--pb-muted);
      width: 32px;
      height: 32px;
      display: grid;
      place-items: center;
      font-size: 0.875rem;
      transition: border-color var(--pb-dur) var(--pb-ease),
        color var(--pb-dur) var(--pb-ease);
    }

    .region__close:hover {
      border-color: var(--pb-blocked);
      color: var(--pb-blocked);
    }

    .region__status {
      display: inline-flex;
      align-items: center;
      gap: 0.375rem;
      padding: 0.3125rem 0.75rem;
      border-radius: var(--pb-radius-pill);
      background: var(--pb-approved-bg);
      color: var(--pb-approved);
      font-weight: 800;
      font-size: 0.6875rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .region__list {
      margin: 0;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: var(--pb-space-3);
      border-top: 1px solid var(--pb-line);
      padding-top: var(--pb-space-3);
    }

    .region__list dt {
      font-family: var(--pb-font-mono);
      font-size: 0.6875rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--pb-muted);
    }

    .region__list dd {
      margin: 0.25rem 0 0;
      color: var(--pb-ink);
      font-size: var(--pb-text-base);
      overflow-wrap: anywhere;
      min-width: 0;
    }

    .region__note {
      display: block;
      margin-top: 0.25rem;
      color: var(--pb-muted);
      font-size: var(--pb-text-sm);
    }

    .region--empty {
      border-style: dashed;
    }

    .region__hint {
      margin-top: var(--pb-space-2);
      color: var(--pb-ink-soft);
      font-size: var(--pb-text-sm);
    }

    @media (max-width: 900px) {
      .map__canvas {
        height: 380px;
      }

      .region__list {
        grid-template-columns: 1fr;
      }
    }
  `,
})
export class CoverageMap implements AfterViewInit, OnDestroy {
  protected readonly regions = signal(REGIONS);
  protected readonly selected = signal<Region | null>(null);

  private readonly mapEl = viewChild.required<ElementRef<HTMLDivElement>>('mapEl');
  private map?: L.Map;
  private markers = new Map<string, L.CircleMarker>();

  async ngAfterViewInit(): Promise<void> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const mod: any = await import('leaflet');
    const L: typeof import('leaflet') = mod.default ?? mod;
    const el = this.mapEl().nativeElement;
    const map = L.map(el, {
      center: [15, 15],
      zoom: 2,
      minZoom: 2,
      maxZoom: 6,
      zoomControl: true,
      attributionControl: true,
      worldCopyJump: false,
    });
    let faded = false;
    const tiles = L.tileLayer(TILE_URL, {
      attribution: TILE_ATTR,
      maxZoom: 6,
      maxNativeZoom: 6,
    }).addTo(map);
    tiles.on('tileerror', () => {
      if (faded) return;
      faded = true;
      tiles.remove();
      L.tileLayer(TILE_FALLBACK_URL, {
        attribution: TILE_FALLBACK_ATTR,
        maxZoom: 6,
        maxNativeZoom: 6,
      }).addTo(map);
    });

    // Hub — the evaluation engine
    L.circleMarker(HUB, {
      radius: 12,
      color: '#5b9e24',
      weight: 2,
      fillColor: '#7cb342',
      fillOpacity: 0.18,
    })
      .addTo(map)
      .bindTooltip('PAYBLOOD ENGINE', { direction: 'top', className: 'pb-tooltip' });

    for (const region of REGIONS) {
      const ll: [number, number] = [region.lat, region.lng];
      L.polyline([HUB, ll], {
        color: '#c2c9ad',
        weight: 1,
        dashArray: '3 6',
        interactive: false,
      }).addTo(map);
      L.polyline([HUB, ll], {
        color: 'transparent',
        weight: 4,
        interactive: false,
      }).addTo(map);

      const marker = L.circleMarker(ll, {
        radius: 7,
        color: '#5b9e24',
        weight: 2,
        fillColor: '#fffdf7',
        fillOpacity: 1,
      })
        .addTo(map)
        .bindTooltip(`${region.country} (${region.iso})`, {
          direction: 'top',
          className: 'pb-tooltip',
        });

      marker.on('click', () => this.selectRegion(region.iso));
      (marker as unknown as { _path?: SVGElement })._path?.setAttribute('data-iso', region.iso);
      this.markers.set(region.iso, marker);
    }

    // Keyboard support: keep markers focusable
    setTimeout(() => {
      this.mapEl().nativeElement.querySelectorAll('.leaflet-interactive').forEach((m) => {
        m.setAttribute('tabindex', '0');
      });
    }, 400);
  }

  ngOnDestroy(): void {
    this.map?.remove();
    this.map = undefined;
  }

  protected selectRegion(iso: string): void {
    const region = this.regions().find((r) => r.iso === iso);
    if (!region) return;
    this.selected.set(region);
    this.map?.panTo([region.lat, region.lng], { animate: true });
    for (const [code, marker] of this.markers) {
      const active = code === iso;
      marker.setStyle(
        active
          ? { color: '#1a1f13', weight: 3, fillColor: '#7cb342', fillOpacity: 1, radius: 8 }
          : { color: '#5b9e24', weight: 2, fillColor: '#fffdf7', fillOpacity: 1, radius: 7 },
      );
      marker.bringToFront();
    }
  }

  protected flagUrl(iso: string): string {
    return `https://flagcdn.com/w40/${iso.toLowerCase()}.png`;
  }

  protected onFlagError(event: Event): void {
    (event.target as HTMLElement).style.visibility = 'hidden';
  }

  protected onMapKey(event: KeyboardEvent): void {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const iso = (event.target as HTMLElement | null)?.getAttribute('data-iso');
    if (iso) {
      event.preventDefault();
      this.selectRegion(iso);
    }
  }

  protected clear(): void {
    this.selected.set(null);
    for (const marker of this.markers.values()) {
      marker.setStyle({ color: '#5b9e24', weight: 2, fillColor: '#fffdf7', fillOpacity: 1, radius: 7 });
    }
  }
}