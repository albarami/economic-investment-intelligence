/** Shared MapLibre and overlay doubles. Each test keeps its own recording hooks. */
import { vi } from 'vitest';

export interface RendererDoubleHooks<
  TMap extends object,
  TOverlay extends object,
> {
  maps: TMap[];
  overlays: TOverlay[];
  events?: string[];
  protocols?: {
    set(name: string, fn: unknown): void;
    delete(name: string): void;
  };
}

function gesture() {
  return { enable: vi.fn(), disable: vi.fn() };
}

export function mapLibreDouble<TMap extends object, TOverlay extends object>(
  hooks: RendererDoubleHooks<TMap, TOverlay>,
) {
  return {
    Map: class {
      dragPan = gesture();
      scrollZoom = gesture();
      boxZoom = gesture();
      dragRotate = gesture();
      doubleClickZoom = gesture();
      touchZoomRotate = gesture();
      touchPitch = gesture();
      keyboard = gesture();
      camera = { center: [0, 0] as number[], zoom: 0, bearing: 0, pitch: 0 };
      style: unknown;
      constructor(options: { style: unknown }) {
        hooks.events?.push('map');
        this.style = options.style;
        hooks.maps.push(this as TMap);
      }
      jumpTo(camera: Partial<typeof this.camera>) {
        this.camera = { ...this.camera, ...camera };
      }
      getCenter() {
        return this.camera.center;
      }
      getZoom() {
        return this.camera.zoom;
      }
      getBearing() {
        return this.camera.bearing;
      }
      getPitch() {
        return this.camera.pitch;
      }
      getBounds() {
        return {
          getWest: () => 51.4,
          getSouth: () => 25.2,
          getEast: () => 51.6,
          getNorth: () => 25.4,
        };
      }
      setStyle(style: unknown) {
        this.style = style;
      }
      on() {}
      off() {}
      remove() {}
      isStyleLoaded() {
        return true;
      }
    },
    setWorkerUrl: vi.fn(),
    setRTLTextPlugin: vi.fn(() => {
      hooks.events?.push('rtl');
      return Promise.resolve();
    }),
    addProtocol: (name: string, fn: unknown) => {
      hooks.protocols?.set(name, fn);
    },
    removeProtocol: (name: string) => {
      hooks.protocols?.delete(name);
    },
  };
}

export function overlayDouble<TMap extends object, TOverlay extends object>(
  hooks: RendererDoubleHooks<TMap, TOverlay>,
) {
  return {
    MapLibreOverlay: class {
      props: unknown;
      constructor(props: unknown) {
        this.props = props;
        hooks.overlays.push(this as TOverlay);
      }
      onAdd() {}
      onRemove() {}
      setProps(props: object) {
        this.props = { ...(this.props as object), ...props };
      }
    },
  };
}
