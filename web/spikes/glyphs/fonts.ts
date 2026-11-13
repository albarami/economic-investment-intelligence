import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans-arabic/400.css';
import notoArabicUrl from '@fontsource/noto-sans-arabic/files/noto-sans-arabic-arabic-400-normal.woff2?url';
import notoLatinUrl from '@fontsource/noto-sans/files/noto-sans-latin-400-normal.woff2?url';

export const REMOTE_FONT_URL = 'https://assets.invalid/font.woff2';
export const LATIN_FACE = 'Noto Sans Regular';
export const ARABIC_FACE = 'Noto Sans Arabic Regular';

const LATIN_RANGE = ['U+0000-024F'];
const ARABIC_RANGE = [
  'U+0600-06FF',
  'U+0750-077F',
  'U+FB50-FDFF',
  'U+FE70-FEFF',
];

export type FontFaceDeclaration = {
  url: string;
  'unicode-range': string[];
};

export type FontFaceMap = Record<string, FontFaceDeclaration[]>;

export function fontFaces(omitArabic: boolean): FontFaceMap {
  const faces: FontFaceMap = {
    [LATIN_FACE]: [{ url: notoLatinUrl, 'unicode-range': LATIN_RANGE }],
  };
  if (!omitArabic) {
    faces[ARABIC_FACE] = [
      { url: notoArabicUrl, 'unicode-range': ARABIC_RANGE },
    ];
  }
  return faces;
}

export function installRemoteFontPlant(): void {
  const link = document.createElement('link');
  link.rel = 'preload';
  link.as = 'font';
  link.href = REMOTE_FONT_URL;
  document.head.append(link);
}
