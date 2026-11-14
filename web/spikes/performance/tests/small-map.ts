import type { Page } from '@playwright/test';
import { SMALL } from './canvas-mode.mjs';

const WALL_WIDTH = '1920px';
const WALL_HEIGHT = '1080px';
const SMALL_WIDTH = '480px';
const SMALL_HEIGHT = '270px';

/**
 * Serves the spike style with a smaller map for this page only.
 * The page source stays at the wall size. A full canvas is unchanged.
 */
export async function prepareCanvas(page: Page, canvas: string): Promise<void> {
  if (canvas !== SMALL) return;
  await page.route('**/*.css', async (route) => {
    const response = await route.fetch();
    const body = (await response.text())
      .replaceAll(WALL_WIDTH, SMALL_WIDTH)
      .replaceAll(WALL_HEIGHT, SMALL_HEIGHT);
    await route.fulfill({ response, body });
  });
}
