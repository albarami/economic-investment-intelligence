/** Text nodes holding a decimal digit of any script outside the Fact chip family. */
export function numeralsOutsideChips(root: ParentNode): string[] {
  const leaked: string[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    const content = node.textContent ?? '';
    if (
      /\p{Nd}/u.test(content) &&
      !node.parentElement?.closest('[data-fact-chip]')
    )
      leaked.push(content);
    node = walker.nextNode();
  }
  return leaked;
}
