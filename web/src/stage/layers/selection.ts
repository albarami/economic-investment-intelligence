/**
 * One selection for map picking and for the named keyboard controls.
 * The overlay publishes; the plate listens.
 */

type Listener = (featureId: string) => void;

let listener: Listener | null = null;

export function bindSelection(next: Listener | null): void {
  listener = next;
}

export function publishSelection(featureId: string): void {
  listener?.(featureId);
}
