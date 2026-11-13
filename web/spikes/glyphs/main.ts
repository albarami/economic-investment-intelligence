import 'maplibre-gl/dist/maplibre-gl.css';
import './style.css';
import { mountMap } from './map';
import { installRemoteFontPlant } from './fonts';
import type { Lang } from './fixtures';

const ARABIC_CHROME =
  'منطقة الاختبار ألف، حي المحاكاة باء، مدينة المثال جيم، قرية العرض دال، شارع التجربة هاء';

function showFailure(message: string): void {
  const node = document.querySelector('#map-failure');
  if (!(node instanceof HTMLElement)) return;
  node.hidden = false;
  node.textContent = message;
}

function readLang(params: URLSearchParams): Lang {
  return params.get('lang') === 'ar' ? 'ar' : 'en';
}

const spike: SpikeDiagnostics = {
  ready: false,
  failure: '',
  labelNames: [],
  webgpu: false,
};
window.__spike = spike;

async function start(): Promise<void> {
  const params = new URLSearchParams(window.location.search);
  const lang = readLang(params);
  const arabic = lang === 'ar';
  document.documentElement.lang = arabic ? 'ar' : 'en';
  document.documentElement.dir = arabic ? 'rtl' : 'ltr';
  const arabicNode = document.querySelector('.chrome-arabic');
  if (arabicNode instanceof HTMLElement) {
    arabicNode.textContent = arabic ? ARABIC_CHROME : '';
  }
  if (params.get('plant') === 'remote-font') installRemoteFontPlant();
  const container = document.querySelector('#map');
  if (!(container instanceof HTMLElement)) {
    spike.failure = 'map container is absent';
    showFailure(spike.failure);
    return;
  }
  try {
    const mounted = await mountMap({
      container,
      lang,
      omitArabic: params.get('plant') === 'omit-arabic-face',
      overlap: params.get('frame') === 'overlap',
    });
    const arabicStyle = getComputedStyle(
      document.querySelector('.chrome-arabic') ?? document.body,
    );
    const latinStyle = getComputedStyle(
      document.querySelector('.chrome-latin') ?? document.body,
    );
    Object.assign(spike, mounted, {
      ready: true,
      failure: '',
      letterSpacing: arabicStyle.letterSpacing,
      direction: getComputedStyle(document.documentElement).direction,
      mirrored: false,
      latinFamily: latinStyle.fontFamily,
      arabicFamily: arabicStyle.fontFamily,
    });
  } catch (error) {
    spike.ready = false;
    spike.failure = error instanceof Error ? error.message : 'map failed';
    showFailure(spike.failure);
  }
}

void start();
