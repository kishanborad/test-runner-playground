export class Locator {
  constructor(
    private doc: Document,
    private selector: string,
  ) {}

  element(): Element | null {
    return this.doc.querySelector(this.selector);
  }

  elements(): NodeListOf<Element> {
    return this.doc.querySelectorAll(this.selector);
  }

  getSelector(): string {
    return this.selector;
  }

  click(): void {
    const el = this.element();
    if (!el) throw new Error(`Element not found: ${this.selector}`);
    (el as HTMLElement).click();
  }

  fill(value: string, iframeWindow?: Window): void {
    const el = this.element();
    if (!el) throw new Error(`Element not found: ${this.selector}`);
    const input = el as HTMLInputElement;
    const win = (iframeWindow ?? window) as unknown as typeof globalThis;
    const setter = Object.getOwnPropertyDescriptor(
      win.HTMLInputElement.prototype,
      'value',
    )?.set;
    if (setter) {
      setter.call(input, value);
    } else {
      input.value = value;
    }
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  textContent(): string {
    const el = this.element();
    if (!el) throw new Error(`Element not found: ${this.selector}`);
    return el.textContent ?? '';
  }
}
