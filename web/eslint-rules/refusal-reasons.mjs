/** Static Part-C gate: a catch must carry the caught value into a closed projection. */
import ts from 'typescript';
export { catalogueParity } from '../scripts/refusal-catalogue.mjs';

function carries(node, name) {
  if (!name) return false;
  let found = false;
  function visit(child) {
    if (
      (ts.isThrowStatement(child) &&
        ts.isIdentifier(child.expression) &&
        child.expression.text === name) ||
      (ts.isCallExpression(child) &&
        ts.isIdentifier(child.expression) &&
        child.expression.text === 'refusalState' &&
        child.arguments[0] &&
        ts.isIdentifier(child.arguments[0]) &&
        child.arguments[0].text === name &&
        !ts.isExpressionStatement(child.parent))
    )
      found = true;
    ts.forEachChild(child, visit);
  }
  visit(node);
  return found;
}
export function refusalViolations(source) {
  const tree = ts.createSourceFile(
    'refusal.tsx',
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const failed = [];
  function visit(node) {
    let body, name;
    if (ts.isCatchClause(node)) {
      body = node.block;
      const binding = node.variableDeclaration?.name;
      name = binding && ts.isIdentifier(binding) ? binding.text : null;
    } else if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.name.text === 'catch'
    ) {
      const callback = node.arguments[0];
      if (
        callback &&
        (ts.isArrowFunction(callback) || ts.isFunctionExpression(callback))
      ) {
        body = callback.body;
        const binding = callback.parameters[0]?.name;
        name = binding && ts.isIdentifier(binding) ? binding.text : null;
      } else body = node;
    }
    if (body && !carries(body, name))
      failed.push(
        tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1,
      );
    ts.forEachChild(node, visit);
  }
  visit(tree);
  return failed;
}

export default {
  meta: {
    type: 'problem',
    schema: [],
    messages: {
      carry:
        'Preserve the caught closed reason through refusalState(error) or rethrow it.',
    },
  },
  create(context) {
    return {
      Program() {
        for (const line of refusalViolations(context.sourceCode.text))
          context.report({ loc: { line, column: 0 }, messageId: 'carry' });
      },
    };
  },
};
