// TST-90's four pinned sizes are present in this checkout; these phone stress
// sizes are provisional. Decision 0049's named sizes are NAMED_SIZES below.
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

/** Decision 0049 item 2: the eight named sizes, phones in both orientations. */
export const NAMED_SIZES = [
  { width: 360, height: 640 },
  { width: 640, height: 360 },
  { width: 390, height: 844 },
  { width: 844, height: 390 },
  { width: 768, height: 1024 },
  { width: 1366, height: 768 },
  { width: 1920, height: 1080 },
  { width: 2560, height: 1440 },
  { width: 3440, height: 1440 },
  { width: 3840, height: 2160 },
] as const;
