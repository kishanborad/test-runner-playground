import { describe, it, expect } from 'vitest';
import { parseTest } from '../engine/parser';

describe('parseTest', () => {
  it('extracts the test name', () => {
    const result = parseTest(`test('My Test', async ({ page }) => {});`);
    expect(result.name).toBe('My Test');
  });

  it('defaults name to Untitled Test when not found', () => {
    const result = parseTest(`await page.goto('/');`);
    expect(result.name).toBe('Untitled Test');
  });

  it('parses page.goto', () => {
    const result = parseTest(`test('t', async ({ page }) => {
      await page.goto('/cart');
    });`);
    expect(result.steps).toHaveLength(1);
    expect(result.steps[0].type).toBe('goto');
    expect(result.steps[0].value).toBe('/cart');
  });

  it('parses page.click', () => {
    const result = parseTest(`test('t', async ({ page }) => {
      await page.click('[data-testid="add-to-cart"]');
    });`);
    expect(result.steps[0].type).toBe('click');
    expect(result.steps[0].selector).toBe('[data-testid="add-to-cart"]');
  });

  it('parses page.fill', () => {
    const result = parseTest(`test('t', async ({ page }) => {
      await page.fill('[data-testid="field-name"]', 'John');
    });`);
    expect(result.steps[0].type).toBe('fill');
    expect(result.steps[0].selector).toBe('[data-testid="field-name"]');
    expect(result.steps[0].value).toBe('John');
  });

  it('parses expect().toBeVisible()', () => {
    const result = parseTest(`test('t', async ({ page }) => {
      await expect(page.locator('[data-testid="product-card"]')).toBeVisible();
    });`);
    expect(result.steps[0].type).toBe('assert-visible');
    expect(result.steps[0].selector).toBe('[data-testid="product-card"]');
  });

  it('parses expect().toHaveText()', () => {
    const result = parseTest(`test('t', async ({ page }) => {
      await expect(page.locator('[data-testid="cart-total"]')).toHaveText('$79.99');
    });`);
    expect(result.steps[0].type).toBe('assert-text');
    expect(result.steps[0].selector).toBe('[data-testid="cart-total"]');
    expect(result.steps[0].expected).toBe('$79.99');
  });

  it('parses expect().toHaveCount()', () => {
    const result = parseTest(`test('t', async ({ page }) => {
      await expect(page.locator('[data-testid="product-card"]')).toHaveCount(10);
    });`);
    expect(result.steps[0].type).toBe('assert-count');
    expect(result.steps[0].selector).toBe('[data-testid="product-card"]');
    expect(result.steps[0].expected).toBe(10);
  });

  it('parses expect().toContainText()', () => {
    const result = parseTest(`test('t', async ({ page }) => {
      await expect(page.locator('[data-testid="product-name"]')).toContainText('Headphones');
    });`);
    expect(result.steps[0].type).toBe('assert-contain-text');
    expect(result.steps[0].selector).toBe('[data-testid="product-name"]');
    expect(result.steps[0].expected).toBe('Headphones');
  });

  it('parses multiple steps in order', () => {
    const result = parseTest(`test('flow', async ({ page }) => {
      await page.goto('/');
      await page.click('[data-testid="add-to-cart"]');
      await expect(page.locator('[data-testid="cart-badge"]')).toBeVisible();
    });`);
    expect(result.steps).toHaveLength(3);
    expect(result.steps[0].type).toBe('goto');
    expect(result.steps[1].type).toBe('click');
    expect(result.steps[2].type).toBe('assert-visible');
  });
});
