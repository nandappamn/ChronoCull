import test from 'node:test';
import assert from 'node:assert/strict';
import { compressWithRTK } from '../src/compression/rtk.js';
import { compressWithCaveman } from '../src/compression/caveman.js';
import { CompressionPipeline } from '../src/compression/pipeline.js';

test('RTK - strips ANSI escape sequences and spinner characters', () => {
  const dirty = '\u001b[32mPASS\u001b[39m ⠋ Compiling project...\nAll checks ok.';
  const res = compressWithRTK(dirty);
  assert.ok(!res.text.includes('\u001b[32m'));
  assert.ok(!res.text.includes('⠋'));
  assert.ok(res.savedChars > 0);
});

test('RTK - collapses verbose test output and keeps summary', () => {
  const testOutput = `
PASS tests/auth.test.js
PASS tests/api.test.js
PASS tests/db.test.js
PASS tests/utils.test.js
Ran 4 test suites. 4 passed.
`;
  const res = compressWithRTK(testOutput);
  assert.ok(res.text.includes('[RTK Summary: 4 passed tests collapsed]'));
  assert.ok(res.text.includes('Ran 4 test suites. 4 passed.'));
  assert.ok(res.savedChars > 20);
});

test('RTK - compresses git diffs and collapses long unchanged context', () => {
  const diff = `diff --git a/src/index.js b/src/index.js
index 83a21bc..94b32de 100644
--- a/src/index.js
+++ b/src/index.js
@@ -10,12 +10,12 @@
 const a = 1;
 const b = 2;
 const c = 3;
 const d = 4;
 const e = 5;
-const f = 6;
+const f = 600;
 const g = 7;
 const h = 8;
 const i = 9;
 const j = 10;
`;
  const res = compressWithRTK(diff);
  assert.ok(!res.text.includes('index 83a21bc..94b32de'));
  assert.ok(res.text.includes('+const f = 600;'));
  assert.ok(res.text.includes('...'));
  assert.ok(res.savedChars > 0);
});

test('Caveman - strips conversational pleasantries and filler', () => {
  const prompt = 'Hello! Sure, I would be happy to help with that. Please note that you need to run tests in order to verify.';
  const res = compressWithCaveman(prompt);
  assert.ok(!res.text.toLowerCase().includes('hello!'));
  assert.ok(!res.text.toLowerCase().includes('happy to help'));
  assert.ok(!res.text.toLowerCase().includes('please note that'));
  assert.ok(res.text.includes('run tests'));
  assert.ok(res.savedChars > 25);
});

test('Caveman - protects code blocks, URLs, and file paths exactly', () => {
  const input = `
Certainly! Here is the code:
\`\`\`javascript
function calculateTotal(items) {
  // https://example.com/api
  return items.map(x => x.price);
}
\`\`\`
Check the file at /Users/developer/project/src/index.js for more details.
`;
  const res = compressWithCaveman(input);
  // Code block must remain 100% intact
  assert.ok(res.text.includes('function calculateTotal(items)'));
  assert.ok(res.text.includes('https://example.com/api'));
  assert.ok(res.text.includes('/Users/developer/project/src/index.js'));
  // Pleasantry should be gone
  assert.ok(!res.text.includes('Certainly!'));
});

test('Stacked Pipeline - applies RTK then Caveman seamlessly', () => {
  const pipeline = new CompressionPipeline({ defaultMode: 'stacked' });
  const payload = {
    model: 'auto',
    messages: [
      {
        role: 'user',
        content: 'Hello! Please note that in order to deploy, run \u001b[32mgit diff\u001b[39m and inspect /var/log/deploy.log'
      }
    ]
  };

  const { payload: compressed, metrics, headerValue } = pipeline.compressChatPayload(payload, 'stacked');
  const resultText = compressed.messages[0].content;

  assert.ok(!resultText.includes('\u001b[32m')); // RTK stripped ANSI
  assert.ok(!resultText.toLowerCase().includes('hello!')); // Caveman stripped greeting
  assert.ok(resultText.includes('/var/log/deploy.log')); // Safe path preserved
  assert.ok(metrics.savedChars > 0);
  assert.ok(headerValue.includes('stacked'));
});
