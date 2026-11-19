export const wording = Object.freeze({
  valid:
    'Catalogue selection checked. Fact display awaits the application component.',
  withheld: 'This result is withheld. Read the coverage reason.',
});
export function checkWording(text: string, withheld: boolean) {
  if (/[\p{Number}]/u.test(text)) throw new Error('TEMPLATE_NUMERAL');
  if (text !== (withheld ? wording.withheld : wording.valid))
    throw new Error('TEMPLATE_TEXT');
  return text;
}
