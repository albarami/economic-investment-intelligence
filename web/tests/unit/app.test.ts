import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { App, EXTRACT_URL } from '../../src/app/App';

const DIGIT = /\p{Nd}/u;

describe('App', () => {
  it('renders an asset-absent stage until the mount names an extract', () => {
    const markup = renderToStaticMarkup(createElement(App));
    expect(markup).toContain('data-state="asset-absent"');
    expect(markup).toContain('data-fragment="opening_electricity_unavailable"');
    expect(markup).toContain('data-scene="opening"');
    expect(markup).toContain('What decision are you making?');
    expect(markup).toContain('data-action="guided-story"');
    expect(markup).not.toContain('data-fragment="foundation_headline"');
    expect(markup).toContain('dir="ltr"');
    expect(markup).toContain('data-part="attribution"');
    expect(markup).not.toContain('SYN-E-');
    expect(markup).not.toContain('pending-native-review');
    const chips = markup.replace(/<span class="chip[^>]*>.*?<\/span>/gs, '');
    const textOnly = chips.replace(/<[^>]*>/g, '');
    expect(DIGIT.test(textOnly)).toBe(false);
  });

  it('requests the mounted extract over the same origin', () => {
    expect(EXTRACT_URL).toBe('/tiles/basemap.pmtiles');
  });
});
