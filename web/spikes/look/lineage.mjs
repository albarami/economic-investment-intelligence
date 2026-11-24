// Closed, versioned producing records shared by release validation and chip
// refusal. Catalogue keys resolve audience wording; origin stays metadata.
export const VERSION = '1.0.0';
export const PIPELINE = { name: 'chain.pipeline', version: VERSION };
export const REGISTER_PIPELINE = {
  name: 'chain.registerPipeline',
  version: VERSION,
};
export const GENERATORS = {
  'chain.pipeline': { version: VERSION, implementation: 'release-build.mjs' },
  'chain.registerPipeline': {
    version: VERSION,
    implementation: 'tools/build_standin.mjs',
  },
};
export const METHODS = Object.fromEntries(
  [
    'chain.methodUnit',
    'chain.methodMean',
    'chain.methodShare',
    'chain.methodBreaks',
    'chain.methodType',
    'chain.methodEmployees',
    'chain.methodBranches',
  ].map((name) => [
    name,
    { version: VERSION, implementation: 'release-build.mjs' },
  ]),
);
const TABLES = [
  'chain.table',
  'chain.tableRegister',
  'chain.tableLabour',
  'chain.tableScale',
];
const nonempty = (value) => typeof value === 'string' && value.trim() !== '';
const hash = (value) =>
  typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
function date(value) {
  return (
    typeof value === 'string' &&
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(`${value}T00:00:00Z`)) &&
    new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value
  );
}
export function validGenerator(value) {
  return (
    value !== null &&
    typeof value === 'object' &&
    typeof value.name === 'string' &&
    Object.hasOwn(GENERATORS, value.name) &&
    GENERATORS[value.name].version === value.version
  );
}
export function validInput(input) {
  if (input === null || typeof input !== 'object' || !hash(input.sha256))
    return false;
  if (input.provenance === 'public') {
    return (
      ['publisher', 'dataset', 'source', 'licence'].every((key) =>
        nonempty(input[key]),
      ) && date(input.retrieved)
    );
  }
  return (
    ['synthetic', 'simulated'].includes(input.provenance) &&
    input.origin === input.provenance &&
    nonempty(input.dataset) &&
    validGenerator(input.generator)
  );
}
export function completeChain(chain) {
  return (
    chain !== null &&
    typeof chain === 'object' &&
    TABLES.includes(chain.table) &&
    typeof chain.method === 'string' &&
    Object.hasOwn(METHODS, chain.method) &&
    METHODS[chain.method].version === chain.method_version &&
    chain.source === 'chain.source' &&
    validGenerator(chain.generator) &&
    Array.isArray(chain.inputs) &&
    chain.inputs.length > 0 &&
    chain.inputs.every(validInput)
  );
}
export function completeFactChain(fact) {
  if (!completeChain(fact.chain)) return false;
  const inputs = fact.chain.inputs.map((input) => input.provenance);
  const declared = fact.input_classes ?? fact.inputClasses;
  if (
    declared !== undefined &&
    (!Array.isArray(declared) ||
      declared.length !== inputs.length ||
      declared.some((value, index) => value !== inputs[index]))
  )
    return false;
  const provenance = inputs.includes('simulated')
    ? 'simulated'
    : inputs.includes('synthetic')
      ? 'synthetic'
      : 'public';
  return (
    fact.provenance === provenance &&
    (provenance === 'public'
      ? fact.origin === undefined
      : fact.origin === provenance)
  );
}
