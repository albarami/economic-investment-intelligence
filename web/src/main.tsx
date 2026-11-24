import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-sans-arabic/400.css';
import '@fontsource/ibm-plex-sans-arabic/500.css';
import '@fontsource/ibm-plex-sans-arabic/600.css';
import './styles/tokens.css';
import './styles/answer.css';
import { App } from './app/App';
import { direction, text } from './i18n';

const container = document.getElementById('root');
if (container === null) {
  throw new Error('The element with id "root" is missing from index.html.');
}

const root = createRoot(container);
const families = [
  { family: 'IBM Plex Sans', sample: text('en', 'opening.question') },
  { family: 'IBM Plex Sans Arabic', sample: text('ar', 'opening.question') },
];
// Demand the actual scripts at every shipped interface weight before the first
// story frame. Missing local font files refuse readiness rather than swapping.
void Promise.all(
  families.flatMap(({ family, sample }) =>
    [400, 500, 600].map((weight) =>
      document.fonts.load(`${weight} 16px "${family}"`, sample),
    ),
  ),
)
  .then((faces) => {
    if (faces.some((loaded) => loaded.length === 0))
      throw new Error('interface_font_absent');
    root.render(
      <StrictMode>
        <App />
      </StrictMode>,
    );
  })
  .catch(() => {
    const language =
      new URLSearchParams(location.search).get('lang') === 'ar' ? 'ar' : 'en';
    root.render(
      <section role="alert" lang={language} dir={direction(language)}>
        {text(language, 'opening.fontsUnavailable')}
      </section>,
    );
  });
