import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import ts from 'typescript';

// Expose real private functions only inside the test VM. Interface substitutes
// are reserved for external failures or the forbidden native CLI lifecycle.
export async function loadModule(url, dependencies, names, globals = {}) {
  const source = fs
    .readFileSync(url, 'utf8')
    .replaceAll('import.meta.url', JSON.stringify(url.href));
  const compiled = ts.transpileModule(
    source + `\nexport {${names.join(',')}};`,
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        esModuleInterop: true,
      },
    },
  ).outputText;
  const exported = {};
  const require = createRequire(url);
  await vm.runInNewContext('(async () => {' + compiled + '})()', {
    exports: exported,
    require: (name) =>
      Object.hasOwn(dependencies, name) ? dependencies[name] : require(name),
    process,
    console,
    Buffer,
    URL,
    Error,
    setTimeout,
    clearTimeout,
    ...globals,
  });
  return exported;
}
