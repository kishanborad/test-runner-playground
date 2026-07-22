import type { TestStep, StepType } from '../types';

const TEST_NAME_RE = /test\(\s*['"](.+?)['"]/;
const GOTO_RE = /page\.goto\(\s*['"](.+?)['"]\s*\)/;
const CLICK_RE = /page\.click\(\s*['"](.+?)['"]\s*\)/;
const FILL_RE = /page\.fill\(\s*['"](.+?)['"]\s*,\s*['"](.+?)['"]\s*\)/;
const EXPECT_VISIBLE_RE = /expect\(page\.locator\(\s*['"](.+?)['"]\s*\)\)\.toBeVisible\(\)/;
const EXPECT_TEXT_RE = /expect\(page\.locator\(\s*['"](.+?)['"]\s*\)\)\.toHaveText\(\s*['"](.+?)['"]\s*\)/;
const EXPECT_COUNT_RE = /expect\(page\.locator\(\s*['"](.+?)['"]\s*\)\)\.toHaveCount\(\s*(\d+)\s*\)/;
const EXPECT_CONTAIN_RE = /expect\(page\.locator\(\s*['"](.+?)['"]\s*\)\)\.toContainText\(\s*['"](.+?)['"]\s*\)/;

interface ParsedLine {
  type: StepType;
  selector?: string;
  value?: string;
  expected?: string | number;
}

function parseLine(line: string): ParsedLine | null {
  let m: RegExpMatchArray | null;

  if ((m = line.match(GOTO_RE))) {
    return { type: 'goto', value: m[1] };
  }
  if ((m = line.match(FILL_RE))) {
    return { type: 'fill', selector: m[1], value: m[2] };
  }
  if ((m = line.match(CLICK_RE))) {
    return { type: 'click', selector: m[1] };
  }
  if ((m = line.match(EXPECT_VISIBLE_RE))) {
    return { type: 'assert-visible', selector: m[1] };
  }
  if ((m = line.match(EXPECT_TEXT_RE))) {
    return { type: 'assert-text', selector: m[1], expected: m[2] };
  }
  if ((m = line.match(EXPECT_COUNT_RE))) {
    return { type: 'assert-count', selector: m[1], expected: parseInt(m[2], 10) };
  }
  if ((m = line.match(EXPECT_CONTAIN_RE))) {
    return { type: 'assert-contain-text', selector: m[1], expected: m[2] };
  }

  return null;
}

export function parseTest(source: string): { name: string; steps: TestStep[] } {
  const nameMatch = source.match(TEST_NAME_RE);
  const name = nameMatch ? nameMatch[1] : 'Untitled Test';

  const lines = source
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.startsWith('await'));

  const steps: TestStep[] = [];

  for (const line of lines) {
    const parsed = parseLine(line);
    if (parsed) {
      steps.push({ ...parsed, raw: line });
    }
  }

  return { name, steps };
}
