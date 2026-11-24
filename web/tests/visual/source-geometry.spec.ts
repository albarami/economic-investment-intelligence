import { expect, test } from '@playwright/test';
for (const kind of ['Point', 'LineString', 'Polygon', 'MultiPolygon'])
  test(`renders ${kind} from its exact source geometry`, async ({ page }) => {
    await page.goto(`/tests/visual/source-geometry.html?kind=${kind}`);
    await expect(page.locator('body')).toHaveAttribute('data-ready', 'true');
    const pick = (lon: number, lat: number) =>
      page.evaluate(
        ([x, y]) =>
          (
            window as unknown as { pickSource(x: number, y: number): boolean }
          ).pickSource(x!, y!),
        [lon, lat],
      );
    if (kind === 'Point') expect(await pick(1, 2)).toBe(true);
    else if (kind === 'LineString') expect(await pick(0.5, 0.5)).toBe(true);
    else {
      // The filled price layer leaves the excluded hole empty.
      expect(await pick(0.5, 0.5)).toBe(true);
      expect(await pick(1, 1.5)).toBe(true);
      expect(await pick(1.5, 1.5)).toBe(false);
      if (kind === 'MultiPolygon') expect(await pick(4.5, 0.5)).toBe(true);
    }
  });
