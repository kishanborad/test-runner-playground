import { Locator } from './locator';

export interface AssertionError {
  message: string;
  expected: string;
  actual: string;
}

function fail(message: string, expected: string, actual: string): never {
  const err = new Error(message) as Error & { expected: string; actual: string };
  err.expected = expected;
  err.actual = actual;
  throw err;
}

export function createExpect(locator: Locator) {
  return {
    toBeVisible() {
      const el = locator.element();
      if (!el) fail(`Element not found: ${locator.getSelector()}`, 'visible', 'not found');
    },

    toHaveText(expected: string) {
      const el = locator.element();
      if (!el) fail(`Element not found: ${locator.getSelector()}`, expected, 'not found');
      const actual = (el.textContent ?? '').trim();
      if (actual !== expected) {
        fail(`Expected text "${expected}" but got "${actual}"`, expected, actual);
      }
    },

    toHaveCount(expected: number) {
      const actual = locator.elements().length;
      if (actual !== expected) {
        fail(`Expected ${expected} elements but found ${actual}`, String(expected), String(actual));
      }
    },

    toContainText(expected: string) {
      const el = locator.element();
      if (!el) fail(`Element not found: ${locator.getSelector()}`, expected, 'not found');
      const actual = (el.textContent ?? '').trim();
      if (!actual.includes(expected)) {
        fail(`Expected text to contain "${expected}" but got "${actual}"`, expected, actual);
      }
    },
  };
}
