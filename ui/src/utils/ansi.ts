export interface AnsiSegment {
  text: string;
  color?: string;
  bold?: boolean;
  dim?: boolean;
  underline?: boolean;
}

const ANSI_COLOR_MAP: Record<number, string> = {
  30: "text-slate-900",
  31: "text-rose-400",
  32: "text-emerald-400",
  33: "text-amber-400",
  34: "text-sky-400",
  35: "text-purple-400",
  36: "text-cyan-400",
  37: "text-slate-200",
  90: "text-slate-500",
  91: "text-rose-300",
  92: "text-emerald-300",
  93: "text-amber-300",
  94: "text-sky-300",
  95: "text-purple-300",
  96: "text-cyan-300",
  97: "text-white",
};

/**
 * Parses a string containing ANSI escape codes into an array of styled segments.
 */
export function parseAnsi(input: string): Array<AnsiSegment> {
  const segments: Array<AnsiSegment> = [];
  // eslint-disable-next-line no-control-regex
  const ansiRegex = /\x1b\[([0-9;]*)m/g;

  let lastIndex = 0;
  let currentColor: string | undefined = undefined;
  let isBold = false;
  let isDim = false;
  let isUnderline = false;

  const pushSegment = (text: string) => {
    if (text.length === 0) return;
    const seg: AnsiSegment = { text };
    if (currentColor) seg.color = currentColor;
    if (isBold) seg.bold = true;
    if (isDim) seg.dim = true;
    if (isUnderline) seg.underline = true;
    segments.push(seg);
  };

  let match: RegExpExecArray | null;
  while ((match = ansiRegex.exec(input)) !== null) {
    pushSegment(input.slice(lastIndex, match.index));

    const codeStr = match[1];
    const codes = codeStr ? codeStr.split(";").map(Number) : [0];

    for (const code of codes) {
      if (code === 0) {
        // Reset
        currentColor = undefined;
        isBold = false;
        isDim = false;
        isUnderline = false;
      } else if (code === 1) {
        isBold = true;
      } else if (code === 2) {
        isDim = true;
      } else if (code === 4) {
        isUnderline = true;
      } else if (code === 22) {
        isBold = false;
        isDim = false;
      } else if (code === 24) {
        isUnderline = false;
      } else if (code === 39) {
        currentColor = undefined;
      } else if (ANSI_COLOR_MAP[code]) {
        currentColor = ANSI_COLOR_MAP[code];
      }
    }

    lastIndex = ansiRegex.lastIndex;
  }

  pushSegment(input.slice(lastIndex));

  return segments;
}

/**
 * Strips all ANSI escape sequences from a string.
 */
export function stripAnsi(input: string): string {
  // eslint-disable-next-line no-control-regex
  return input.replace(/\x1b\[[0-9;]*m/g, "");
}
