// npx tsx scripts/typst-text-check.ts — or `npm run check:typst`.
// sidereal-core's fixture is the contract: `lib/typstText.ts` must answer it exactly as
// `sidereal_core.typst_text` does.
import fixture from "../../../sidereal-core/tests/fixtures/typst_text.json";

import { plainText } from "../src/lib/typstText";

const wrong = fixture.vectors.filter(({ typst, text }) => plainText(typst) !== text);

for (const { typst, text } of wrong) {
  console.error(
    `${JSON.stringify(typst)}\n  want ${JSON.stringify(text)}\n  got  ${JSON.stringify(plainText(typst))}`
  );
}

if (wrong.length > 0) {
  throw new Error(`typstText: ${String(wrong.length)} of ${String(fixture.vectors.length)} vectors differ.`);
}

console.log(`typstText: all ${String(fixture.vectors.length)} vectors match.`);
