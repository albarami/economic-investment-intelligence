// TST-90's four pinned sizes are present in this checkout. Decision 0049's
// additional sizes are absent; these phone stress sizes are provisional.
export const PHONE_VIEWPORTS = [
  { width: 320, height: 568 },
  { width: 375, height: 667 },
  { width: 390, height: 844 },
  { width: 430, height: 932 },
] as const;

export const ANSWER_VIEWPORTS = [
  { width: 3840, height: 2160 },
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1024, height: 768 },
  ...PHONE_VIEWPORTS,
] as const;
