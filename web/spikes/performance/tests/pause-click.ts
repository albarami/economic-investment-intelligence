import type { Page } from '@playwright/test';

export async function clickPause(page: Page): Promise<void> {
  const point = await page.evaluate(async () => {
    const button = document.querySelector<HTMLButtonElement>('#pause-motion');
    if (!button) throw new Error('pause click refused: absent');
    const check = () => {
      if (
        !button.isConnected ||
        !button.checkVisibility({ checkVisibilityCSS: true })
      ) {
        throw new Error('pause click refused: hidden');
      }
      if (button.matches(':disabled'))
        throw new Error('pause click refused: disabled');
      for (
        let element: Element | null = button;
        element;
        element = element.parentElement
      ) {
        const disabled = element.getAttribute('aria-disabled')?.toLowerCase();
        if (disabled === 'true')
          throw new Error('pause click refused: disabled');
        if (disabled === 'false') break;
      }
      if (button.closest('[inert]'))
        throw new Error('pause click refused: inert');
      const box = button.getBoundingClientRect();
      if (box.width <= 0 || box.height <= 0)
        throw new Error('pause click refused: hidden');
      return { x: box.x, y: box.y, width: box.width, height: box.height };
    };
    const initial = check();
    if (
      initial.x < 0 ||
      initial.y < 0 ||
      initial.x + initial.width > innerWidth ||
      initial.y + initial.height > innerHeight
    ) {
      button.scrollIntoView({
        block: 'center',
        inline: 'center',
        behavior: 'instant',
      });
    }
    // Keep the two-frame stability check, but do not issue a separate protocol
    // round trip for every property while the full software scene is drawing.
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => resolve()),
    );
    const before = check();
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => resolve()),
    );
    const after = check();
    if (JSON.stringify(before) !== JSON.stringify(after)) {
      throw new Error('pause click refused: unstable');
    }
    const x = after.x + after.width / 2;
    const y = after.y + after.height / 2;
    const target = document.elementFromPoint(x, y);
    if (!target || !button.contains(target))
      throw new Error('pause click refused: covered');
    button.removeAttribute('data-spike-click-received');
    button.addEventListener(
      'click',
      (event) => {
        button.setAttribute(
          'data-spike-click-received',
          event.isTrusted ? 'trusted' : 'untrusted',
        );
      },
      { once: true },
    );
    return { x, y };
  });
  // This is browser mouse input, never a synthetic click or dispatchEvent.
  await page.mouse.click(point.x, point.y);
  await page.evaluate(() => {
    const button = document.querySelector('#pause-motion');
    const received = button?.getAttribute('data-spike-click-received');
    button?.removeAttribute('data-spike-click-received');
    if (received !== 'trusted') throw new Error('pause click refused: missed');
  });
}
