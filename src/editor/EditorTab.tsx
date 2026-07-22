import Editor, { type OnMount } from '@monaco-editor/react';
import type { editor, languages, IPosition } from 'monaco-editor';

const PLAYWRIGHT_COMPLETIONS: languages.CompletionItem[] = [
  { label: "page.goto('')", kind: 1, insertText: "page.goto('${1:url}')", insertTextRules: 4, detail: 'Navigate to URL', range: undefined as never },
  { label: "page.click('')", kind: 1, insertText: "page.click('${1:selector}')", insertTextRules: 4, detail: 'Click element', range: undefined as never },
  { label: "page.fill('', '')", kind: 1, insertText: "page.fill('${1:selector}', '${2:value}')", insertTextRules: 4, detail: 'Fill input', range: undefined as never },
  { label: "page.locator('')", kind: 1, insertText: "page.locator('${1:selector}')", insertTextRules: 4, detail: 'Create locator', range: undefined as never },
  { label: 'expect().toBeVisible()', kind: 1, insertText: "expect(page.locator('${1:selector}')).toBeVisible()", insertTextRules: 4, detail: 'Assert visible', range: undefined as never },
  { label: "expect().toHaveText('')", kind: 1, insertText: "expect(page.locator('${1:selector}')).toHaveText('${2:text}')", insertTextRules: 4, detail: 'Assert text', range: undefined as never },
  { label: 'expect().toHaveCount()', kind: 1, insertText: "expect(page.locator('${1:selector}')).toHaveCount(${2:count})", insertTextRules: 4, detail: 'Assert count', range: undefined as never },
  { label: "expect().toContainText('')", kind: 1, insertText: "expect(page.locator('${1:selector}')).toContainText('${2:text}')", insertTextRules: 4, detail: 'Assert contains text', range: undefined as never },
];

const TEST_TEMPLATE = `test('My Test', async ({ page }) => {
  await page.goto('/');
  // Write your test steps here
});`;

interface Props {
  source: string;
  onChange: (value: string) => void;
}

export default function EditorTab({ source, onChange }: Props) {
  const handleMount: OnMount = (_editor: editor.IStandaloneCodeEditor, monaco) => {
    monaco.languages.registerCompletionItemProvider('typescript', {
      provideCompletionItems: (_model: editor.ITextModel, position: IPosition) => {
        const word = _model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };
        return {
          suggestions: PLAYWRIGHT_COMPLETIONS.map((c) => ({ ...c, range })),
        };
      },
    });
  };

  return (
    <Editor
      height="100%"
      language="typescript"
      theme="vs-dark"
      value={source || TEST_TEMPLATE}
      onChange={(v) => onChange(v ?? '')}
      onMount={handleMount}
      options={{
        minimap: { enabled: false },
        fontSize: 13,
        lineNumbers: 'on',
        scrollBeyondLastLine: false,
        wordWrap: 'on',
        tabSize: 2,
        automaticLayout: true,
      }}
    />
  );
}
