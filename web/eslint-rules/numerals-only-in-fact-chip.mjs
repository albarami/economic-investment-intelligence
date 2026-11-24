/**
 * FE-39: numerals reach the screen only through the Fact chip family.
 * A numeral is any Unicode Nd character. Case 3 asks the TypeScript parser
 * services for number and bigint; if those services are missing the rule
 * reports, and does not treat the file as clean.
 */
import ts from 'typescript';

const NUMERAL = /\p{Nd}/u;

/** The value/reference/operational chip, typed input chip and their formatter. */
export const FACT_CHIP_FILES = [
  'src/facts/FactChip.tsx',
  'src/facts/NumericInput.tsx',
  'src/facts/formatters.ts',
];

const RENDERED_ATTRIBUTES = new Set([
  'title',
  'alt',
  'placeholder',
  'label',
  'aria-label',
  'aria-description',
  'aria-valuetext',
]);

const BANNED_METHODS = new Set(['toLocaleString', 'toFixed', 'toPrecision']);

const INTL_FORMATTERS = new Set(['NumberFormat', 'DateTimeFormat']);

/** Name fields the style generator may draw. `label` is the glyph spike's place-name field. */
export const NAME_FIELDS = new Set([
  'name',
  'name:en',
  'name:ar',
  'name:latin',
  'name:nonlatin',
  'label',
]);

const NUMBER_FLAGS =
  ts.TypeFlags.Number |
  ts.TypeFlags.NumberLiteral |
  ts.TypeFlags.NumberLike |
  ts.TypeFlags.BigInt |
  ts.TypeFlags.BigIntLiteral |
  ts.TypeFlags.BigIntLike;

function hasNumeral(value) {
  return typeof value === 'string' && NUMERAL.test(value);
}

function attributeName(node) {
  if (!node || node.type !== 'JSXAttribute' || !node.name) return '';
  if (node.name.type === 'JSXIdentifier') return node.name.name;
  return '';
}

function exemptFile(filename) {
  const norm = String(filename ?? '')
    .split('\\')
    .join('/');
  if (
    FACT_CHIP_FILES.some((file) => norm === file || norm.endsWith('/' + file))
  )
    return true;
  if (/(^|\/)(tests|fixtures)\//.test(norm)) return true;
  if (/\.(test|spec)\.[cm]?[jt]sx?$/.test(norm)) return true;
  if (/(^|\/)spikes\/performance\//.test(norm)) return true;
  return false;
}

function isRenderedContainer(node) {
  const parent = node.parent;
  if (!parent) return false;
  if (parent.type === 'JSXElement' || parent.type === 'JSXFragment')
    return true;
  if (parent.type === 'JSXAttribute')
    return RENDERED_ATTRIBUTES.has(attributeName(parent));
  return false;
}

function templateIsRendered(node) {
  const parent = node.parent;
  if (!parent || parent.type !== 'JSXExpressionContainer') return false;
  return isRenderedContainer(parent);
}

function literalIsRendered(node) {
  const parent = node.parent;
  if (!parent) return false;
  if (parent.type === 'JSXAttribute')
    return RENDERED_ATTRIBUTES.has(attributeName(parent));
  if (parent.type === 'JSXExpressionContainer')
    return isRenderedContainer(parent);
  if (parent.type === 'TemplateLiteral') return templateIsRendered(parent);
  return false;
}

function servicesOf(context) {
  const services = context.sourceCode?.parserServices;
  const map = services?.esTreeNodeToTSNodeMap;
  const program = services?.program;
  if (!map || !program || typeof map.get !== 'function') return null;
  return { map, program };
}

function isNumericType(type, seen) {
  if (!type || seen.has(type)) return false;
  seen.add(type);
  if (typeof type.isUnion === 'function' && type.isUnion())
    return type.types.some((part) => isNumericType(part, seen));
  if (typeof type.isIntersection === 'function' && type.isIntersection())
    return type.types.some((part) => isNumericType(part, seen));
  if (type.flags & NUMBER_FLAGS) return true;
  if (type.flags & ts.TypeFlags.TypeParameter) {
    const constraint = type.getConstraint();
    return constraint ? isNumericType(constraint, seen) : false;
  }
  return false;
}

/** @returns {'numeric' | 'other' | 'missing'} */
function numericKind(context, node) {
  const services = servicesOf(context);
  if (!services) return 'missing';
  const tsNode = services.map.get(node);
  if (!tsNode) return 'missing';
  const type = services.program.getTypeChecker().getTypeAtLocation(tsNode);
  return isNumericType(type, new Set()) ? 'numeric' : 'other';
}

function needsType(node) {
  if (!node) return false;
  if (node.type === 'Literal') return false;
  if (node.type === 'JSXElement' || node.type === 'JSXFragment') return false;
  if (node.type === 'TemplateLiteral') return true;
  return true;
}

function bannedName(node) {
  const callee = node.callee;
  if (!callee || callee.type !== 'MemberExpression' || callee.computed)
    return '';
  if (callee.property.type !== 'Identifier') return '';
  const name = callee.property.name;
  if (BANNED_METHODS.has(name)) return name;
  if (!INTL_FORMATTERS.has(name)) return '';
  const object = callee.object;
  if (object.type === 'Identifier' && object.name === 'Intl')
    return `Intl.${name}`;
  return '';
}

function isTextLayerCallee(callee, aliases) {
  if (!callee) return false;
  if (callee.type === 'Identifier') return aliases.has(callee.name);
  if (
    callee.type === 'MemberExpression' &&
    !callee.computed &&
    callee.property.type === 'Identifier'
  )
    return callee.property.name === 'TextLayer';
  return false;
}

function walkTextField(context, node) {
  if (!node || node.type !== 'ArrayExpression') return;
  const head = node.elements[0];
  if (head && head.type === 'Literal' && head.value === 'get') {
    const prop = node.elements[1];
    const allowed =
      prop &&
      prop.type === 'Literal' &&
      typeof prop.value === 'string' &&
      NAME_FIELDS.has(prop.value);
    if (!allowed) {
      context.report({ node: prop ?? node, messageId: 'text-field' });
    }
  }
  for (const element of node.elements) {
    if (element && element.type === 'ArrayExpression')
      walkTextField(context, element);
  }
}

const rule = {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Numerals reach the screen only through the Fact chip family.',
    },
    schema: [],
    messages: {
      'jsx-text':
        'A numeral is rendered outside the Fact chip family (JSX text).',
      'jsx-string':
        'A numeral is rendered outside the Fact chip family (string).',
      'jsx-number':
        'A number or bigint is rendered outside the Fact chip family.',
      'banned-call':
        'Formatting calls belong in web/src/facts/formatters.ts ({{name}}).',
      'text-layer': 'deck.gl TextLayer is outside the Fact chip family.',
      'text-field':
        'A MapLibre text-field reads a property that is not an allowed name field.',
      'missing-services':
        'The numeral rule needs TypeScript parser services and did not receive them.',
    },
  },
  create(context) {
    if (exemptFile(context.filename)) return {};
    const aliases = new Set(['TextLayer']);

    function inspectRendered(node) {
      if (!node || !needsType(node)) return;
      if (node.type === 'TemplateLiteral') {
        for (const expression of node.expressions) inspectRendered(expression);
        return;
      }
      const kind = numericKind(context, node);
      if (kind === 'missing') {
        context.report({ node, messageId: 'missing-services' });
        return;
      }
      if (kind === 'numeric') context.report({ node, messageId: 'jsx-number' });
    }

    return {
      JSXText(node) {
        if (hasNumeral(node.value))
          context.report({ node, messageId: 'jsx-text' });
      },
      Literal(node) {
        if (!literalIsRendered(node)) return;
        if (typeof node.value === 'string' && hasNumeral(node.value))
          context.report({ node, messageId: 'jsx-string' });
        if (typeof node.value === 'number' || node.bigint)
          context.report({ node, messageId: 'jsx-number' });
      },
      TemplateElement(node) {
        if (!templateIsRendered(node.parent)) return;
        const cooked = node.value?.cooked ?? node.value?.raw ?? '';
        if (hasNumeral(cooked))
          context.report({ node, messageId: 'jsx-string' });
      },
      JSXExpressionContainer(node) {
        if (!isRenderedContainer(node)) return;
        inspectRendered(node.expression);
      },
      CallExpression(node) {
        const name = bannedName(node);
        if (name)
          context.report({ node, messageId: 'banned-call', data: { name } });
        if (isTextLayerCallee(node.callee, aliases))
          context.report({ node, messageId: 'text-layer' });
      },
      NewExpression(node) {
        const name = bannedName(node);
        if (name)
          context.report({ node, messageId: 'banned-call', data: { name } });
        if (isTextLayerCallee(node.callee, aliases))
          context.report({ node, messageId: 'text-layer' });
      },
      ImportDeclaration(node) {
        for (const specifier of node.specifiers) {
          if (
            specifier.type === 'ImportSpecifier' &&
            specifier.imported.type === 'Identifier' &&
            specifier.imported.name === 'TextLayer'
          )
            aliases.add(specifier.local.name);
        }
      },
      VariableDeclarator(node) {
        if (
          node.id.type === 'Identifier' &&
          node.init &&
          node.init.type === 'Identifier' &&
          aliases.has(node.init.name)
        )
          aliases.add(node.id.name);
      },
      Property(node) {
        if (node.computed) return;
        const key = node.key;
        const name =
          key.type === 'Identifier'
            ? key.name
            : key.type === 'Literal'
              ? key.value
              : '';
        if (name !== 'text-field') return;
        walkTextField(context, node.value);
      },
    };
  },
};

export default rule;
