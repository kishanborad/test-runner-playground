import type { TestStep, StepResult } from '../types';
import { Locator } from './locator';
import { createExpect } from './assertions';

export interface HighlightInfo {
  rect: { top: number; left: number; width: number; height: number };
  label: string;
  success: boolean;
}

export interface ExecutorCallbacks {
  onStepStart: (index: number, step: TestStep) => void;
  onStepComplete: (index: number, result: StepResult) => void;
  onComplete: (results: StepResult[]) => void;
  onCursorMove: (x: number, y: number) => Promise<void>;
  onHighlight: (info: HighlightInfo | null) => void;
  onScreenshot: (index: number) => Promise<string | undefined>;
}

export interface ExecutorOptions {
  stepDelay: number;
  cursorDuration: number;
  highlightDuration: number;
}

const DEFAULT_OPTIONS: ExecutorOptions = {
  stepDelay: 500,
  cursorDuration: 300,
  highlightDuration: 200,
};

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function describeStep(step: TestStep): string {
  switch (step.type) {
    case 'goto':
      return `Navigate to "${step.value}"`;
    case 'click':
      return `Click "${step.selector}"`;
    case 'fill':
      return `Fill "${step.selector}" with "${step.value}"`;
    case 'assert-visible':
      return `Assert "${step.selector}" is visible`;
    case 'assert-text':
      return `Assert "${step.selector}" has text "${step.expected}"`;
    case 'assert-count':
      return `Assert "${step.selector}" count is ${step.expected}`;
    case 'assert-contain-text':
      return `Assert "${step.selector}" contains "${step.expected}"`;
  }
}

function getElementCenter(el: Element): { x: number; y: number } {
  const rect = el.getBoundingClientRect();
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
}

function getElementRect(el: Element): HighlightInfo['rect'] {
  const rect = el.getBoundingClientRect();
  return { top: rect.top, left: rect.left, width: rect.width, height: rect.height };
}

export async function executeTest(
  steps: TestStep[],
  iframe: HTMLIFrameElement,
  callbacks: ExecutorCallbacks,
  options: Partial<ExecutorOptions> = {},
): Promise<StepResult[]> {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const doc = iframe.contentDocument;
  const win = iframe.contentWindow;

  if (!doc || !win) {
    throw new Error(
      'Cannot access iframe document. This usually means the URL is cross-origin. ' +
      'The test engine can only interact with same-origin pages.',
    );
  }

  const results: StepResult[] = [];

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    callbacks.onStepStart(i, step);
    const start = performance.now();

    try {
      if (step.type === 'goto') {
        win.location.hash = '#' + (step.value ?? '/');
        await delay(300);
      } else {
        const selector = step.selector!;
        const locator = new Locator(doc, selector);
        const el = locator.element();

        if (el) {
          const center = getElementCenter(el);
          await callbacks.onCursorMove(center.x, center.y);
          await delay(opts.cursorDuration);
        }

        const label = describeStep(step);

        switch (step.type) {
          case 'click': {
            if (!el) throw new Error(`Element not found: ${selector}`);
            callbacks.onHighlight({ rect: getElementRect(el), label, success: true });
            await delay(opts.highlightDuration);
            locator.click();
            break;
          }
          case 'fill': {
            if (!el) throw new Error(`Element not found: ${selector}`);
            callbacks.onHighlight({ rect: getElementRect(el), label, success: true });
            await delay(opts.highlightDuration);
            locator.fill(step.value ?? '', win);
            break;
          }
          case 'assert-visible': {
            const assertion = createExpect(locator);
            assertion.toBeVisible();
            callbacks.onHighlight({ rect: getElementRect(el!), label, success: true });
            await delay(opts.highlightDuration);
            break;
          }
          case 'assert-text': {
            const assertion = createExpect(locator);
            assertion.toHaveText(String(step.expected ?? ''));
            callbacks.onHighlight({ rect: getElementRect(el!), label, success: true });
            await delay(opts.highlightDuration);
            break;
          }
          case 'assert-count': {
            const assertion = createExpect(locator);
            assertion.toHaveCount(Number(step.expected ?? 0));
            const firstEl = locator.element();
            if (firstEl) {
              callbacks.onHighlight({ rect: getElementRect(firstEl), label, success: true });
              await delay(opts.highlightDuration);
            }
            break;
          }
          case 'assert-contain-text': {
            const assertion = createExpect(locator);
            assertion.toContainText(String(step.expected ?? ''));
            callbacks.onHighlight({ rect: getElementRect(el!), label, success: true });
            await delay(opts.highlightDuration);
            break;
          }
        }
      }

      const duration = performance.now() - start;
      const screenshot = await callbacks.onScreenshot(i);
      const result: StepResult = { step, status: 'passed', duration, screenshot };
      results.push(result);
      callbacks.onStepComplete(i, result);
    } catch (err) {
      const duration = performance.now() - start;
      const error = err instanceof Error ? err.message : String(err);
      const errObj = err as Error & { expected?: string; actual?: string };

      if (step.selector) {
        const el = doc.querySelector(step.selector);
        if (el) {
          callbacks.onHighlight({
            rect: getElementRect(el),
            label: describeStep(step),
            success: false,
          });
          await delay(opts.highlightDuration);
        }
      }

      const screenshot = await callbacks.onScreenshot(i);
      const result: StepResult = {
        step,
        status: 'failed',
        duration,
        screenshot,
        error,
        expected: errObj.expected,
        actual: errObj.actual,
      };
      results.push(result);
      callbacks.onStepComplete(i, result);
    }

    callbacks.onHighlight(null);
    await delay(opts.stepDelay);
  }

  callbacks.onComplete(results);
  return results;
}
