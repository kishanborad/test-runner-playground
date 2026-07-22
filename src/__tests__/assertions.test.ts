import { describe, it, expect, beforeEach } from 'vitest';
import { Locator } from '../engine/locator';
import { createExpect } from '../engine/assertions';

describe('assertions', () => {
  let doc: Document;

  beforeEach(() => {
    doc = document;
    document.body.innerHTML = `
      <div data-testid="visible">Hello World</div>
      <div data-testid="items"><span>A</span><span>B</span><span>C</span></div>
    `;
  });

  it('toBeVisible passes for visible element', () => {
    const locator = new Locator(doc, '[data-testid="visible"]');
    expect(() => createExpect(locator).toBeVisible()).not.toThrow();
  });

  it('toBeVisible fails for missing element', () => {
    const locator = new Locator(doc, '[data-testid="nope"]');
    expect(() => createExpect(locator).toBeVisible()).toThrow('not found');
  });

  it('toHaveText passes with matching text', () => {
    const locator = new Locator(doc, '[data-testid="visible"]');
    expect(() => createExpect(locator).toHaveText('Hello World')).not.toThrow();
  });

  it('toHaveText fails with wrong text', () => {
    const locator = new Locator(doc, '[data-testid="visible"]');
    expect(() => createExpect(locator).toHaveText('Goodbye')).toThrow();
  });

  it('toHaveCount passes with correct count', () => {
    const locator = new Locator(doc, '[data-testid="items"] span');
    expect(() => createExpect(locator).toHaveCount(3)).not.toThrow();
  });

  it('toHaveCount fails with wrong count', () => {
    const locator = new Locator(doc, '[data-testid="items"] span');
    expect(() => createExpect(locator).toHaveCount(5)).toThrow();
  });

  it('toContainText passes when text is included', () => {
    const locator = new Locator(doc, '[data-testid="visible"]');
    expect(() => createExpect(locator).toContainText('Hello')).not.toThrow();
  });

  it('toContainText fails when text is missing', () => {
    const locator = new Locator(doc, '[data-testid="visible"]');
    expect(() => createExpect(locator).toContainText('Missing')).toThrow();
  });
});
