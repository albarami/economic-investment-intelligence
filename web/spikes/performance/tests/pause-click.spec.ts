import { expect, test } from '@playwright/test';
import { clickPause } from './pause-click';

const button = '<button id="pause-motion">Pause motion</button>';

test('pause pointer helper sends a trusted click to the enabled button', async ({
  page,
}) => {
  await page.setContent(button);
  await page.locator('#pause-motion').evaluate((element) => {
    element.addEventListener('click', (event) => {
      element.setAttribute('data-trusted', String(event.isTrusted));
    });
  });
  await clickPause(page);
  await expect(page.locator('#pause-motion')).toHaveAttribute(
    'data-trusted',
    'true',
  );
});

for (const [name, markup] of [
  ['absent', '<p>No pause control</p>'],
  ['hidden', '<button id="pause-motion" hidden>Pause motion</button>'],
  ['disabled', '<button id="pause-motion" disabled>Pause motion</button>'],
  ['inert', '<div inert>' + button + '</div>'],
  [
    'covered',
    button + '<div style="position:fixed;inset:0;background:white"></div>',
  ],
] as const) {
  test(`pause pointer helper refuses a ${name} button`, async ({ page }) => {
    page.setDefaultTimeout(500);
    await page.setContent(markup);
    await expect(clickPause(page)).rejects.toThrow(
      `pause click refused: ${name}`,
    );
  });
}

test('pause pointer helper refuses a moving button', async ({ page }) => {
  await page.setContent(button);
  await page.locator('#pause-motion').evaluate((element) => {
    let left = 0;
    const move = () => {
      (element as HTMLElement).style.marginLeft = `${left++}px`;
      requestAnimationFrame(move);
    };
    requestAnimationFrame(move);
  });
  page.setDefaultTimeout(500);
  await expect(clickPause(page)).rejects.toThrow(
    'pause click refused: unstable',
  );
});

test('pause pointer helper refuses a click intercepted after preparation', async ({
  page,
}) => {
  await page.setContent(button);
  await page.evaluate(() => {
    document.addEventListener(
      'pointermove',
      () => {
        const cover = document.createElement('div');
        cover.style.cssText = 'position:fixed;inset:0;background:white';
        document.body.append(cover);
      },
      { once: true },
    );
  });
  page.setDefaultTimeout(500);
  await expect(clickPause(page)).rejects.toThrow('pause click refused: missed');
});

test('pause pointer helper refuses a zero-area button', async ({ page }) => {
  await page.setContent(
    '<button id="pause-motion" style="width:0;height:0;padding:0;border:0">Pause motion</button>',
  );
  await expect(clickPause(page)).rejects.toThrow('pause click refused: hidden');
});

test('pause pointer helper refuses an aria-disabled button', async ({
  page,
}) => {
  await page.setContent(
    '<button id="pause-motion" aria-disabled="TRUE">Pause motion</button>',
  );
  await expect(clickPause(page)).rejects.toThrow(
    'pause click refused: disabled',
  );
});

test('pause pointer helper refuses inherited aria-disabled state', async ({
  page,
}) => {
  await page.setContent('<div aria-disabled="true">' + button + '</div>');
  await expect(clickPause(page)).rejects.toThrow(
    'pause click refused: disabled',
  );
});

test('pause pointer helper honors an explicit aria-disabled false override', async ({
  page,
}) => {
  await page.setContent(
    '<div aria-disabled="true"><button id="pause-motion" aria-disabled="false">Pause motion</button></div>',
  );
  await clickPause(page);
});

test('pause pointer helper scrolls an offscreen button into view before clicking', async ({
  page,
}) => {
  await page.setContent('<div style="height:2000px"></div>' + button);
  await page.locator('#pause-motion').evaluate((element) => {
    element.addEventListener('click', (event) => {
      element.setAttribute('data-trusted', String(event.isTrusted));
    });
  });
  await clickPause(page);
  await expect(page.locator('#pause-motion')).toBeInViewport();
  await expect(page.locator('#pause-motion')).toHaveAttribute(
    'data-trusted',
    'true',
  );
});
