import type { PrewrittenTest } from '../types';

export const prewrittenTests: PrewrittenTest[] = [
  {
    id: 'browse-products',
    name: 'Browse products',
    source: `test('Browse products', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('[data-testid="product-card"]')).toHaveCount(10);
  await expect(page.locator('[data-testid="product-name"]')).toBeVisible();
  await expect(page.locator('[data-testid="product-price"]')).toBeVisible();
});`,
  },
  {
    id: 'search-filter',
    name: 'Search and filter',
    source: `test('Search and filter', async ({ page }) => {
  await page.goto('/');
  await page.fill('[data-testid="search-input"]', 'Keyboard');
  await expect(page.locator('[data-testid="product-card"]')).toHaveCount(1);
  await expect(page.locator('[data-testid="product-name"]')).toContainText('Keyboard');
});`,
  },
  {
    id: 'add-to-cart',
    name: 'Add to cart',
    source: `test('Add to cart', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-testid="add-to-cart"]');
  await expect(page.locator('[data-testid="cart-badge"]')).toBeVisible();
  await expect(page.locator('[data-testid="cart-badge"]')).toHaveText('1');
});`,
  },
  {
    id: 'update-quantity',
    name: 'Update cart quantity',
    source: `test('Update cart quantity', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-testid="add-to-cart"]');
  await page.goto('/cart');
  await page.click('[data-testid="quantity-plus"]');
  await expect(page.locator('[data-testid="quantity"]')).toHaveText('2');
});`,
  },
  {
    id: 'remove-from-cart',
    name: 'Remove from cart',
    source: `test('Remove from cart', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-testid="add-to-cart"]');
  await page.goto('/cart');
  await expect(page.locator('[data-testid="cart-item"]')).toHaveCount(1);
  await page.click('[data-testid="remove-item"]');
  await expect(page.locator('[data-testid="empty-cart"]')).toBeVisible();
});`,
  },
  {
    id: 'checkout-flow',
    name: 'Checkout flow',
    source: `test('Checkout flow', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-testid="add-to-cart"]');
  await page.goto('/cart');
  await page.click('[data-testid="checkout-btn"]');
  await page.fill('[data-testid="field-name"]', 'Jane Doe');
  await page.fill('[data-testid="field-email"]', 'jane@example.com');
  await page.fill('[data-testid="field-address"]', '123 Main St');
  await page.fill('[data-testid="field-city"]', 'Springfield');
  await page.fill('[data-testid="field-zip"]', '62701');
  await page.click('[data-testid="submit-order"]');
  await expect(page.locator('[data-testid="order-confirmation"]')).toBeVisible();
});`,
  },
  {
    id: 'form-validation',
    name: 'Form validation',
    source: `test('Form validation', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-testid="add-to-cart"]');
  await page.goto('/checkout');
  await page.click('[data-testid="submit-order"]');
  await expect(page.locator('[data-testid="error-message"]')).toBeVisible();
});`,
  },
  {
    id: 'responsive-nav',
    name: 'Responsive layout',
    source: `test('Responsive layout', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('[data-testid="nav-toggle"]')).toBeVisible();
  await page.click('[data-testid="nav-toggle"]');
  await expect(page.locator('[data-testid="nav-menu"]')).toBeVisible();
});`,
  },
];
