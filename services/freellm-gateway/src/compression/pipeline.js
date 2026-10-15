import { compressWithRTK } from './rtk.js';
import { compressWithCaveman } from './caveman.js';

/**
 * Stacked Compression Pipeline (RTK -> Caveman)
 * 
 * In stacked mode:
 * 1. RTK cleans terminal output, git diffs, test logs, ANSI codes, and tracebacks.
 * 2. Caveman strips conversational filler, hedging, and unnecessary formatting while keeping code safe.
 */
export class CompressionPipeline {
  /**
   * @param {Object} [options]
   * @param {'off'|'rtk'|'caveman'|'stacked'} [options.defaultMode='stacked']
   */
  constructor(options = {}) {
    this.defaultMode = options.defaultMode || 'stacked';
  }

  /**
   * Compress a single text block according to the requested mode
   * @param {string} text
   * @param {'off'|'rtk'|'caveman'|'stacked'} [mode]
   * @param {string} [role]
   */
  compressText(text, mode = this.defaultMode, role = 'user') {
    if (!text || mode === 'off') {
      return {
        text,
        originalChars: text ? text.length : 0,
        compressedChars: text ? text.length : 0,
        savedChars: 0,
        estTokensSaved: 0,
        rtkSavedChars: 0,
        cavemanSavedChars: 0
      };
    }

    const originalChars = text.length;
    let current = text;
    let rtkSavedChars = 0;
    let cavemanSavedChars = 0;

    // Apply RTK if mode is rtk or stacked (or if message is a tool output)
    if (mode === 'rtk' || mode === 'stacked' || role === 'tool') {
      const rtkRes = compressWithRTK(current);
      current = rtkRes.text;
      rtkSavedChars = rtkRes.savedChars;
    }

    // Apply Caveman if mode is caveman or stacked (unless role is purely raw tool data)
    if (mode === 'caveman' || mode === 'stacked') {
      const cmRes = compressWithCaveman(current);
      current = cmRes.text;
      cavemanSavedChars = cmRes.savedChars;
    }

    const compressedChars = current.length;
    const totalSavedChars = Math.max(0, originalChars - compressedChars);
    const estTokensSaved = Math.round(totalSavedChars / 4);

    return {
      text: current,
      originalChars,
      compressedChars,
      savedChars: totalSavedChars,
      estTokensSaved,
      rtkSavedChars,
      cavemanSavedChars
    };
  }

  /**
   * Compress an OpenAI Chat Completions payload
   * @param {Object} payload { messages: Array<{ role: string, content: string | any[] }>, ... }
   * @param {'off'|'rtk'|'caveman'|'stacked'} [mode]
   * @returns {{ payload: Object, metrics: Object, headerValue: string }}
   */
  compressChatPayload(payload, mode = this.defaultMode) {
    if (!payload || !Array.isArray(payload.messages) || mode === 'off') {
      return {
        payload,
        metrics: { mode: 'off', originalChars: 0, compressedChars: 0, totalSavedChars: 0, estTokensSaved: 0 },
        headerValue: 'off; saved~=0'
      };
    }

    let totalOriginalChars = 0;
    let totalCompressedChars = 0;
    let totalRtkSaved = 0;
    let totalCavemanSaved = 0;

    const compressedMessages = payload.messages.map(msg => {
      if (typeof msg.content === 'string') {
        const res = this.compressText(msg.content, mode, msg.role);
        totalOriginalChars += res.originalChars;
        totalCompressedChars += res.compressedChars;
        totalRtkSaved += res.rtkSavedChars;
        totalCavemanSaved += res.cavemanSavedChars;
        return { ...msg, content: res.text };
      } else if (Array.isArray(msg.content)) {
        // Multi-part content (e.g. text + image_url)
        const parts = msg.content.map(part => {
          if (part && part.type === 'text' && typeof part.text === 'string') {
            const res = this.compressText(part.text, mode, msg.role);
            totalOriginalChars += res.originalChars;
            totalCompressedChars += res.compressedChars;
            totalRtkSaved += res.rtkSavedChars;
            totalCavemanSaved += res.cavemanSavedChars;
            return { ...part, text: res.text };
          }
          return part;
        });
        return { ...msg, content: parts };
      }
      return msg;
    });

    const totalSavedChars = Math.max(0, totalOriginalChars - totalCompressedChars);
    const estTokensSaved = Math.round(totalSavedChars / 4);

    const metrics = {
      mode,
      originalChars: totalOriginalChars,
      compressedChars: totalCompressedChars,
      savedChars: totalSavedChars,
      estTokensSaved,
      rtkSavedChars: totalRtkSaved,
      cavemanSavedChars: totalCavemanSaved
    };

    const headerValue = `${mode}; rtk_saved=${totalRtkSaved}; caveman_saved=${totalCavemanSaved}; saved~=${estTokensSaved}`;

    return {
      payload: { ...payload, messages: compressedMessages },
      metrics,
      headerValue
    };
  }
}
