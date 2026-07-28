# Test Runner Playground

A browser-based Playwright-style test runner. Write tests against an embedded demo shop and watch them execute live — animated cursor, element highlights, step-by-step results, and downloadable reports. No server, no API keys, runs entirely in the browser.

**Live demo:** [kishanborad.github.io/test-runner-playground](https://kishanborad.github.io/test-runner-playground/)

## What it does

Three-panel layout:

- **Left** — pick from 12 pre-written tests or write your own in a Monaco editor with Playwright API autocomplete
- **Center** — an embedded mini e-commerce shop running in an iframe. During execution, an animated cursor moves to each element, highlights flash green/red, and tooltips show what's happening
- **Right** — live execution log with pass/fail indicators, step timing, and expandable screenshot previews. After a run, download an HTML report or a video recording

## Pre-written tests

| Test | What it covers |
|------|---------------|
| Browse products | 10 product cards render with names, prices, images |
| Search and filter | Search by name, verify filtered results |
| Add to cart | Click "Add to Cart", verify badge + cart contents |
| Update cart quantity | Change quantity, verify price recalculates |
| Remove from cart | Remove item, verify empty cart state |
| Checkout flow | Fill shipping form, submit, verify order confirmation |
| Form validation | Submit empty form, verify error messages |
| Responsive layout | Toggle mobile nav menu |
| Search with no results | Search for nonexistent product, verify zero cards |
| Empty cart state | Navigate to cart without items, verify empty message |
| Partial form validation | Fill only some fields, verify errors block checkout |
| Quantity minimum boundary | Verify quantity cannot decrease below 1 |

## Supported Playwright API

```typescript
// Navigation
await page.goto('/cart');

// Actions
await page.click('[data-testid="add-to-cart"]');
await page.fill('[data-testid="field-name"]', 'Jane Doe');

// Assertions
await expect(page.locator('[data-testid="product-card"]')).toBeVisible();
await expect(page.locator('[data-testid="cart-total"]')).toHaveText('$79.99');
await expect(page.locator('[data-testid="product-card"]')).toHaveCount(10);
await expect(page.locator('[data-testid="product-name"]')).toContainText('Keyboard');
```

## The demo shop

A small React e-commerce app with four pages: product list with search, product detail, shopping cart with quantity controls, and checkout with form validation. Static data, no external API calls.

## Getting started

```bash
git clone https://github.com/kishanborad/test-runner-playground.git
cd test-runner-playground
npm install
npm run dev
```

Open `http://localhost:5173` for the test runner and `http://localhost:5173/shop.html` for the shop standalone.

## Scripts

```bash
npm run dev        # Start dev server
npm run build      # Production build
npm run preview    # Preview production build
npm test           # Run unit tests (Vitest)
npm run typecheck  # TypeScript check
npm run deploy     # Deploy to GitHub Pages
```

## Tech stack

- React 18 + TypeScript
- Vite 5
- Tailwind CSS 3
- Monaco Editor
- html2canvas (screenshot capture)
- Canvas API + MediaRecorder (video recording)
- Vitest (unit tests)
- GitHub Pages (hosting)

## Project structure

```
src/
  shop/           # Mini e-commerce app (runs in iframe)
    data.ts         Product data (10 items)
    CartContext.tsx  Cart state provider
    ShopNav.tsx     Nav bar with cart badge
    ProductList.tsx Product grid + search
    ProductDetail.tsx Single product view
    Cart.tsx        Cart with quantity controls
    Checkout.tsx    Shipping form + validation
  engine/         # Test execution engine
    parser.ts       Regex-based Playwright syntax parser
    locator.ts      DOM query wrapper
    assertions.ts   expect() matchers
    executor.ts     Step-by-step runner with callbacks
  overlay/        # Visual feedback layer
    Overlay.tsx     Animated cursor + element highlights
  panels/         # UI panels
    TestListPanel.tsx Left panel (test list + editor tabs)
    ShopPanel.tsx     Center panel (iframe + overlay)
    ReportPanel.tsx   Right panel (log + report + downloads)
    StepRow.tsx       Single step row
  editor/         # Code editor
    EditorTab.tsx   Monaco with Playwright autocomplete
  report/         # Export utilities
    generateReport.ts Self-contained HTML report builder
    videoRecorder.ts  MediaRecorder wrapper
  tests/          # Pre-written test definitions
    prewritten.ts   12 test cases (8 happy path + 4 failure scenarios)
  types.ts        # Shared TypeScript types
  App.tsx         # Root component (three-panel layout)
```

## Custom URL mode

Paste any URL in the input field to run tests against an external site instead of the built-in shop. Cross-origin iframes will show a clear error message since DOM access is blocked by browser security.

## AI tools

Built with [Claude Code](https://claude.ai/code) as the AI copilot for code generation, agent-driven development, and automated testing workflows.

## Author

Kishan Borad
- [GitHub](https://github.com/kishanborad)
- [LinkedIn](https://linkedin.com/in/kishanborad27)

## License

MIT — see [LICENSE](LICENSE).
