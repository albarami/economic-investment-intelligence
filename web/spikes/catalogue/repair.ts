import type {
  Context,
  Dispatcher,
  Oracle,
  Refusal,
} from './native-dispatch.ts';

export function conversation(original: readonly string[]) {
  const prefix = [...original];
  let repaired = false;
  function verify(history: readonly string[]) {
    if (
      history.length !== prefix.length ||
      history.some((turn, index) => turn !== prefix[index])
    )
      throw new Error('HISTORY');
  }
  return {
    repair(history: readonly string[], failure: Refusal) {
      verify(history);
      if (repaired) throw new Error('REPAIR_LIMIT');
      repaired = true;
      // Only a fixed request and validator-produced rule/path; no facts or generated wording.
      const request = JSON.stringify({
        role: 'user',
        request: 'Correct structured data',
        rule: failure.rule_code,
        path: failure.item_path,
      });
      prefix.push(request);
      return [...prefix];
    },
    verify,
  };
}
export async function fallback(
  dispatch: Dispatcher,
  raw: string,
  context: Context,
  oracle: Oracle,
) {
  const result = await dispatch.prepare(raw, context, oracle);
  if (!result.receipt) throw new Error('FALLBACK');
  dispatch.commit(result.receipt);
  return { writer: 'template', label: 'Written by template' };
}

export async function resolveAnswer(
  outcome: string,
  first: string,
  repaired: string,
  template: string,
  context: Context,
  oracle: Oracle,
  dispatch: Dispatcher,
  history: readonly string[],
) {
  if (
    !['answer', 'refusal', 'max_tokens', 'api_error', 'timeout'].includes(
      outcome,
    )
  )
    throw new Error('OUTCOME');
  const session = conversation(history);
  if (outcome !== 'answer')
    return {
      ...(await fallback(dispatch, template, context, oracle)),
      history: [...history],
    };
  const initial = await dispatch.prepare(first, context, oracle);
  if (initial.receipt) {
    dispatch.commit(initial.receipt);
    return { writer: 'catalogue', history: [...history] };
  }
  if (!initial.refusal) throw new Error('REFUSAL');
  const appended = session.repair(history, initial.refusal);
  const second = await dispatch.prepare(repaired, context, oracle);
  session.verify(appended);
  if (second.receipt) {
    dispatch.commit(second.receipt);
    return { writer: 'catalogue', history: appended };
  }
  return {
    ...(await fallback(dispatch, template, context, oracle)),
    history: appended,
  };
}
