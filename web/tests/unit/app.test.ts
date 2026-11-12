import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { App } from '../../src/app/App';

describe('App', () => {
  it('renders the empty main landmark of the shell', () => {
    expect(renderToStaticMarkup(createElement(App))).toBe(
      '<main id="shell"></main>',
    );
  });
});
