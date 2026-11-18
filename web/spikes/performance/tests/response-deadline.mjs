// A deadline for the entire response, including a peer that keeps sending data.
export function waitForResponse(start, milliseconds = 5000) {
  return new Promise((resolve, reject) => {
    let cancel;
    const finish = (callback, value) => {
      clearTimeout(timer);
      callback(value);
    };
    const timer = setTimeout(() => {
      try {
        cancel?.();
      } finally {
        reject(new Error('response-timeout'));
      }
    }, milliseconds);
    try {
      cancel = start(
        (value) => finish(resolve, value),
        (error) => finish(reject, error),
      );
    } catch (error) {
      finish(reject, error);
    }
  });
}
