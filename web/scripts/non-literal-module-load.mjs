import fs from 'node:fs';
import path from 'node:path';

const NON_LITERAL_LOAD_EXCEPTIONS = [
  {
    file: 'tests/check-dev-server.node-test.mjs',
    form: 'import()',
    argument: '${pathToFileURL(SCRIPT).href}?timed=${t.name}',
  },
  {
    file: 'tests/photoreal-assets.node-test.mjs',
    form: 'import()',
    argument: 'data:text/javascript,${encodeURIComponent(changed)}',
  },
];

function scriptRelative(file, scripts) {
  try {
    return path.relative(fs.realpathSync(scripts), fs.realpathSync(file));
  } catch {
    return null;
  }
}

function allowedNonLiteralLoad(item, file, scripts) {
  if (item.argumentKind !== 'template') return false;
  const relative = scriptRelative(file, scripts);
  return NON_LITERAL_LOAD_EXCEPTIONS.some(
    (row) =>
      row.file === relative &&
      row.form === item.form &&
      row.argument === item.argument,
  );
}

export function nonLiteralModuleLoadViolations(items, file, scripts) {
  return items.flatMap((item) => {
    if (item.form !== 'import()' && item.form !== 'require()') return [];
    if (allowedNonLiteralLoad(item, file, scripts)) return [];
    return [{ ...item, reason: 'non-literal-module-load' }];
  });
}
