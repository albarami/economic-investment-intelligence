export type Refusal = { rule_code: string; item_path: string };
export type OracleAnswer = { refusal: Refusal | null; checks: string[] };
export type Context = Record<string, unknown>;
export type Oracle = (raw: string, context: Context) => Promise<OracleAnswer>;
export type Selection = { brief: Record<string, unknown>; withheld: boolean };
const checks = [
  'schema_and_invention',
  'sources',
  'assumptions',
  'scope',
  'limits_and_companions',
];

export async function validate(raw: string, context: Context, oracle: Oracle) {
  const answer = await oracle(raw, context);
  if (answer.refusal) return { ...answer, severity: 'blocking' as const };
  if (JSON.stringify(answer.checks) !== JSON.stringify(checks)) {
    return {
      refusal: { rule_code: 'ACCOUNTING', item_path: 'checks' },
      checks: answer.checks,
      severity: 'blocking' as const,
    };
  }
  return { ...answer, severity: null };
}

export function createDispatcher(
  sink: (selection: Selection) => void,
  applicationActivation = () => false,
) {
  const receipts = new WeakMap<object, Selection>();
  const activations = new WeakSet<object>();
  const committed = new WeakSet<object>();
  async function prepare(raw: string, context: Context, oracle: Oracle) {
    // Snapshot before an asynchronous oracle; neither caller nor adapter may edit it later.
    const snapshot = structuredClone(context);
    const result = await validate(raw, snapshot, oracle);
    if (result.refusal) return { ...result, receipt: null };
    const receipt = Object.freeze({});
    receipts.set(receipt, {
      brief: JSON.parse(raw) as Record<string, unknown>,
      withheld: snapshot.withheld === true,
    });
    return { ...result, receipt };
  }
  function commit(receipt: object | null) {
    const selection = receipt && receipts.get(receipt);
    if (!receipt || !selection || committed.has(receipt))
      throw new Error('RECEIPT');
    committed.add(receipt);
    sink(structuredClone(selection));
  }
  function activate() {
    // The host reads real user activation. Model payloads never enter this function.
    if (!applicationActivation()) throw new Error('ACTIVATION');
    const token = Object.freeze({});
    activations.add(token);
    queueMicrotask(() => activations.delete(token));
    return token;
  }
  function action(receipt: object, value: unknown, activation?: object) {
    if (!receipts.has(receipt) || !committed.has(receipt))
      throw new Error('RECEIPT');
    if (!value || typeof value !== 'object') throw new Error('ACTION');
    const row = value as Record<string, unknown>;
    if (
      JSON.stringify(Object.keys(row)) !==
        JSON.stringify(['key', 'side_effect']) ||
      row.key !== 'save_view' ||
      row.side_effect !== true
    )
      throw new Error('ACTION');
    if (!activation || !activations.has(activation))
      throw new Error('ACTIVATION');
    activations.delete(activation);
    return 'saved_view';
  }
  return { prepare, commit, activate, action };
}
export type Dispatcher = ReturnType<typeof createDispatcher>;
async function entry(
  dispatch: Dispatcher,
  raw: string,
  context: Context,
  oracle: Oracle,
) {
  const result = await dispatch.prepare(raw, context, oracle);
  if (result.receipt) dispatch.commit(result.receipt);
  return result.refusal;
}
export function story(
  dispatch: Dispatcher,
  raw: string,
  context: Context,
  oracle: Oracle,
) {
  return entry(dispatch, raw, context, oracle);
}
export function explore(
  dispatch: Dispatcher,
  raw: string,
  context: Context,
  oracle: Oracle,
) {
  return entry(dispatch, raw, context, oracle);
}
export function assistant(
  dispatch: Dispatcher,
  raw: string,
  context: Context,
  oracle: Oracle,
) {
  return entry(dispatch, raw, context, oracle);
}

export function negotiate(version: string, supported: ReadonlySet<string>) {
  if (!supported.has(version)) throw new Error('CATALOGUE_VERSION');
  return version;
}
export function severity(refusal: Refusal | null, proposed: string) {
  if (refusal && proposed !== 'blocking') throw new Error('SEVERITY');
  if (!['blocking', 'warning'].includes(proposed)) throw new Error('SEVERITY');
  return proposed;
}
