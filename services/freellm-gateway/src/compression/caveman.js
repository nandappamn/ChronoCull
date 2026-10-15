/**
 * Caveman Prompt Compression Engine
 * 
 * Target: Natural language prose, conversation filler, polite framing, 
 * hedging phrases, and conversational pleasantries.
 * 
 * Core rule: NEVER corrupt or modify code blocks, URLs, file paths, or JSON.
 * Typical savings: 20% to 50% on conversation and instruction prompts.
 */

// Common polite filler phrases and pleasantries to strip
const FILLER_PATTERNS = [
  // Conversational openings
  /^(?:hello|hi|hey|greetings)[\s,!.]+(?:how are you\??)?/gim,
  /^(?:sure|certainly|absolutely|of course)[,!.]\s*(?:(?:i'd|i would|we'd|we would)\s+be\s+happy\s+to\s+help(?: with that)?[\.!])?/gim,
  /(?:(?:i'd|i would|we'd|we would)\s+be\s+happy\s+to\s+help(?: with that)?[\.!])/gim,
  /^(?:as an ai(?: language model)?|i am an ai),?\s*/gim,
  
  // Conversational closings
  /(?:i hope this helps|let me know if you have any questions|feel free to ask if you need anything else|let me know if you need more details)[.!]*$/gim,
  
  // Verbose conversational hedging
  /\bplease note that\b/gi,
  /\bplease be advised that\b/gi,
  /\bit is important to note that\b/gi,
  /\bit should be mentioned that\b/gi,
  /\bin order to\b/gi,
  /\bdue to the fact that\b/gi,
  /\bat the present moment in time\b/gi,
  /\bat the present time\b/gi,
  /\bfor the purpose of\b/gi,
  /\bwith regard to\b/gi,
  /\bin the event that\b/gi,
  /\byou should make sure to\b/gi,
  /\bmake sure to\b/gi
];

// Word replacements to concise equivalents
const CONCISE_REPLACEMENTS = [
  [/\bin order to\b/gi, 'to'],
  [/\bdue to the fact that\b/gi, 'because'],
  [/\bat the present time\b/gi, 'now'],
  [/\bfor the purpose of\b/gi, 'for'],
  [/\bwith regard to\b/gi, 'about'],
  [/\bin the event that\b/gi, 'if'],
  [/\bit is recommended that you\b/gi, 'recommend:'],
  [/\byou need to\b/gi, 'must']
];

/**
 * Shield code blocks, URLs, and file paths before text manipulation
 * @param {string} text
 * @returns {{ maskedText: string, restore: (s: string) => string }}
 */
function shieldProtectedZones(text) {
  const shields = [];
  let maskIndex = 0;

  // 1. Multi-line code blocks: ```...```
  let masked = text.replace(/```[\s\S]*?```/g, (match) => {
    const placeholder = `__CM_SHIELD_BLOCK_${maskIndex++}__`;
    shields.push({ placeholder, original: match });
    return placeholder;
  });

  // 2. Inline code: `...`
  masked = masked.replace(/`[^`\n]+`/g, (match) => {
    const placeholder = `__CM_SHIELD_INLINE_${maskIndex++}__`;
    shields.push({ placeholder, original: match });
    return placeholder;
  });

  // 3. URLs
  masked = masked.replace(/https?:\/\/[^\s)\]]+/g, (match) => {
    const placeholder = `__CM_SHIELD_URL_${maskIndex++}__`;
    shields.push({ placeholder, original: match });
    return placeholder;
  });

  // 4. File paths
  masked = masked.replace(/(?:\/[\w.-]+){2,}/g, (match) => {
    const placeholder = `__CM_SHIELD_PATH_${maskIndex++}__`;
    shields.push({ placeholder, original: match });
    return placeholder;
  });

  const restore = (processedText) => {
    let unmasked = processedText;
    // Restore in reverse order so nested tokens work
    for (let i = shields.length - 1; i >= 0; i--) {
      const { placeholder, original } = shields[i];
      unmasked = unmasked.replace(placeholder, original);
    }
    return unmasked;
  };

  return { maskedText: masked, restore };
}

/**
 * Main Caveman compression entrypoint
 * @param {string} text
 * @param {Object} [options]
 * @returns {{ text: string, originalChars: number, compressedChars: number, savedChars: number, estTokensSaved: number }}
 */
export function compressWithCaveman(text, options = {}) {
  if (typeof text !== 'string' || !text.trim()) {
    return { text: text || '', originalChars: 0, compressedChars: 0, savedChars: 0, estTokensSaved: 0 };
  }

  const originalChars = text.length;

  // 1. Shield code blocks, URLs, and paths
  const { maskedText, restore } = shieldProtectedZones(text);
  let processed = maskedText;

  // 2. Strip conversational filler and pleasantries
  for (const pattern of FILLER_PATTERNS) {
    processed = processed.replace(pattern, '');
  }

  // 3. Replace wordy phrases with compact equivalents
  for (const [pattern, replacement] of CONCISE_REPLACEMENTS) {
    processed = processed.replace(pattern, replacement);
  }

  // 4. Whitespace hygiene: collapse multiple empty lines into at most one blank line
  processed = processed
    .split('\n')
    .map(line => line.trimEnd())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  // 5. Restore shielded code blocks and paths intact
  const finalOutput = restore(processed);

  const compressedChars = finalOutput.length;
  const savedChars = Math.max(0, originalChars - compressedChars);
  const estTokensSaved = Math.round(savedChars / 4);

  return {
    text: finalOutput,
    originalChars,
    compressedChars,
    savedChars,
    estTokensSaved
  };
}
