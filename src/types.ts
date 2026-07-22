export type StepType =
  | 'goto'
  | 'click'
  | 'fill'
  | 'assert-visible'
  | 'assert-text'
  | 'assert-count'
  | 'assert-contain-text';

export interface TestStep {
  type: StepType;
  selector?: string;
  value?: string;
  expected?: string | number;
  raw: string;
}

export type StepStatus = 'pending' | 'running' | 'passed' | 'failed';

export interface StepResult {
  step: TestStep;
  status: StepStatus;
  duration: number;
  screenshot?: string;
  error?: string;
  expected?: string;
  actual?: string;
}

export interface TestRun {
  name: string;
  startedAt: number;
  completedAt?: number;
  steps: StepResult[];
}

export interface PrewrittenTest {
  id: string;
  name: string;
  source: string;
}
