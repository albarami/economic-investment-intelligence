import { expect, it } from 'vitest';
import ar from '../../src/i18n/ar.json';
import en from '../../src/i18n/en.json';
import { fragmentField } from '../../src/brief/catalogue';

it('keeps the reviewed Arabic opening instructions and captions exactly', () => {
  expect(ar.strings['draw.moveVertex']).toBe(
    'المس الموضع الجديد لنقل النقطة المحددة.',
  );
  expect(ar.strings['draw.gazetteerOnly']).toBe(
    'يجري البحث في قائمة الأماكن المحفوظة على الجهاز.',
  );
  expect(ar.strings['layers.choose']).toBe('بيانات الخريطة');
  expect(ar.strings['story.cards']).toBe('شواهد السياق');
  expect(ar.strings['opening.action.talent']).toBe('الكفاءات');
  expect(ar.strings['story.busyness']).toBe('عرض الانشغال النسبي في');
  expect(en.strings['story.busyness']).toBe('Read relative busyness at');
});
it('keeps the unavailable opening figure and radiance caveat in the closed bilingual catalogue', () => {
  expect(fragmentField('opening_electricity_unavailable', 'template_ar')).toBe(
    'مؤشر الكهرباء في شاشة البداية غير متاح في هذا الإصدار.',
  );
  expect(fragmentField('opening_electricity_unavailable', 'template_en')).toBe(
    'The electricity figure for the opening screen is unavailable in this release.',
  );
  expect(fragmentField('night_lights_not_activity', 'template_ar')).toBe(
    'الضوء الليلي من NASA Black Marble ليس مقياسًا للنشاط التجاري.',
  );
});
