/** Sun calculation stays in the pinned renderer; angles follow reference S22. */
import { _SunLight as SunLight } from '@deck.gl/core';

export function lightPosition(
  direction: readonly number[],
): [number, number, number] {
  const [x = 0, y = 0, z = 0] = direction;
  const degrees = 180 / Math.PI;
  const azimuth = (Math.atan2(-x, -y) * degrees + 360) % 360;
  const polar = Math.acos(-z / Math.hypot(x, y, z)) * degrees;
  return [1, azimuth, polar];
}

/** Incoming light points upward when the sun is below the horizon. */
export function nightVisible(direction: readonly number[]): boolean {
  return (direction[2] ?? 0) > 0;
}

export class ClockLight extends SunLight {
  constructor(
    timestamp: number,
    private readonly report: (direction: number[]) => void,
    shadow = false,
  ) {
    // deck.gl's shadow is experimental (LightingEffect, DirectionalLight pages).
    super({ timestamp, _shadow: shadow });
  }
  override getProjectedLight(
    parameters: Parameters<SunLight['getProjectedLight']>[0],
  ) {
    const projected = super.getProjectedLight(parameters);
    this.report(projected.direction);
    return projected;
  }
}
