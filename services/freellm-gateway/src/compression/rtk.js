/**
 * RTK (Recursive Token Killer)
 * Command, Terminal, and Tool Output Compression Engine.
 * 
 * Target: Strips noise, progress bars, ANSI codes, verbose test logs, 
 * redundant git diff headers, and internal stack traces.
 * Typical token savings: 50% to 90% on command output.
 */

// Strip ANSI control and escape sequences
const ANSI_REGEX = /[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g;

// Strip terminal spinner characters and progress indicators
const SPINNER_REGEX = /[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏◐◓◑◒←↖↑↗→↘↓↙]/g;

// Progress bars: e.g. [=====>    ] 45% or 45% [=====>    ] or 12/45 (50%)
const PROGRESS_BAR_REGEX = /(?:\[[=#>-]+\]|\b\d{1,3}%\s*\[[=#>-]+\]|\[\s*\d+\s*\/\s*\d+\s*\])/g;

/**
 * Compress a Git Diff payload
 * @param {string} text
 * @returns {string}
 */
export function compressGitDiff(text) {
  const lines = text.split('\n');
  const result = [];
  let inHunk = false;
  let consecutiveContext = 0;

  for (const line of lines) {
    // Drop index hashes and file mode lines
    if (/^index [0-9a-f]{7,40}\.\.[0-9a-f]{7,40}/.test(line)) continue;
    if (/^new file mode \d+/.test(line)) continue;
    if (/^deleted file mode \d+/.test(line)) continue;
    if (/^similarity index \d+%/.test(line)) continue;

    // Track hunk headers: @@ -1,5 +1,6 @@
    if (/^@@ -\d+.* \+\d+.* @@/.test(line)) {
      inHunk = true;
      consecutiveContext = 0;
      result.push(line);
      continue;
    }

    if (inHunk) {
      if (line.startsWith('+') || line.startsWith('-')) {
        consecutiveContext = 0;
        result.push(line);
      } else if (line.startsWith(' ')) {
        // Limit unchanged context lines to max 2 around changes
        consecutiveContext++;
        if (consecutiveContext <= 2) {
          result.push(line);
        } else if (consecutiveContext === 3) {
          result.push('   ...');
        }
      } else {
        result.push(line);
      }
    } else {
      result.push(line);
    }
  }

  return result.join('\n');
}

/**
 * Compress Test Suite Outputs (Jest, Pytest, Go test, Cargo test)
 * @param {string} text
 * @returns {string}
 */
export function compressTestOutput(text) {
  const lines = text.split('\n');
  const result = [];
  let passedCount = 0;

  for (const line of lines) {
    const trimmed = line.trim();
    // Collapse individual PASS lines
    if (/^(?:PASS|✓|\✔|ok\s+)\s+/i.test(trimmed)) {
      passedCount++;
      continue;
    }

    // Collapse repetitive pytest dots
    if (/^[\.\s]{10,}$/.test(trimmed)) {
      continue;
    }

    result.push(line);
  }

  if (passedCount >= 2) {
    result.unshift(`[RTK Summary: ${passedCount} passed tests collapsed]`);
  } else if (passedCount === 1) {
    // If only 1 passed, keep as brief pass note
    result.unshift('✓ passed');
  }

  return result.join('\n');
}

/**
 * Compress Stack Traces (collapse node:internal, site-packages, etc.)
 * @param {string} text
 * @returns {string}
 */
export function compressStackTraces(text) {
  const lines = text.split('\n');
  const result = [];
  let internalOmitted = 0;

  for (const line of lines) {
    const isInternalFrame = 
      /^\s+at\s+.*(?:\(node:internal\/|node_modules\/|site-packages\/|dist\/vendor)/.test(line) ||
      /^\s+File ".*(?:site-packages|dist-packages|lib\/python\d\.\d+)\//.test(line);

    if (isInternalFrame) {
      internalOmitted++;
      continue;
    } else {
      if (internalOmitted > 0) {
        result.push(`    ... [${internalOmitted} internal runtime frames collapsed]`);
        internalOmitted = 0;
      }
      result.push(line);
    }
  }

  if (internalOmitted > 0) {
    result.push(`    ... [${internalOmitted} internal runtime frames collapsed]`);
  }

  return result.join('\n');
}

/**
 * Head & Tail Limiter for massive command / tool outputs
 * @param {string} text
 * @param {number} [maxLines=80]
 * @returns {string}
 */
export function limitOutputHeadTail(text, maxLines = 80) {
  const lines = text.split('\n');
  if (lines.length <= maxLines) return text;

  const keepHead = Math.floor(maxLines * 0.4);
  const keepTail = Math.floor(maxLines * 0.4);
  const omitted = lines.length - keepHead - keepTail;

  const head = lines.slice(0, keepHead);
  const tail = lines.slice(lines.length - keepTail);

  return [
    ...head,
    `\n[... RTK: ${omitted} lines of command output omitted ...]\n`,
    ...tail
  ].join('\n');
}

/**
 * Main RTK entrypoint
 * @param {string} text
 * @param {Object} [options]
 * @returns {{ text: string, originalChars: number, compressedChars: number, savedChars: number, estTokensSaved: number }}
 */
export function compressWithRTK(text, options = {}) {
  if (typeof text !== 'string' || !text.trim()) {
    return { text: text || '', originalChars: 0, compressedChars: 0, savedChars: 0, estTokensSaved: 0 };
  }

  const originalChars = text.length;

  // 1. Strip ANSI escape sequences & terminal spinners
  let processed = text.replace(ANSI_REGEX, '').replace(SPINNER_REGEX, '');

  // 2. Strip progress bars
  processed = processed.replace(PROGRESS_BAR_REGEX, '');

  // 3. Compress Git diffs if detected
  if (/^diff --git/m.test(processed) || /^--- a\//m.test(processed)) {
    processed = compressGitDiff(processed);
  }

  // 4. Compress test runner noise if detected
  if (/(?:PASS|pytest|FAILED|Ran \d+ tests)/i.test(processed)) {
    processed = compressTestOutput(processed);
  }

  // 5. Compress internal stack traces
  if (/(?:\s+at\s+.*\(node:|Traceback \(most recent call last\):)/.test(processed)) {
    processed = compressStackTraces(processed);
  }

  // 6. Limit excessive output length
  const maxLines = options.maxLines || 100;
  processed = limitOutputHeadTail(processed, maxLines);

  const compressedChars = processed.length;
  const savedChars = Math.max(0, originalChars - compressedChars);
  const estTokensSaved = Math.round(savedChars / 4);

  return {
    text: processed,
    originalChars,
    compressedChars,
    savedChars,
    estTokensSaved
  };
}
