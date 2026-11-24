/** The one stylesheet input of the cards' en/ar layout contract, shared by
 * the browser capture (`answers.spec.ts`) and the unit caller
 * (`contract.test.tsx`). It holds the sheets in the application's load
 * order: `tokens.css` and `answer.css` from `src/main.tsx`, then the card's
 * own sheet, so the language-conditioned token definitions are in the graph.
 */
import { readFileSync } from 'node:fs';

export const CARD_STYLES: readonly string[] = [
  readFileSync('src/styles/tokens.css', 'utf8'),
  readFileSync('src/styles/answer.css', 'utf8'),
  readFileSync('src/cards/public-context.css', 'utf8'),
];
