import { JsonValue } from '../types/api';

const NUMERIC_PATTERN = /^-?\d+(\.\d+)?$/;

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];

    if (char === '"') {
      const next = line[i + 1];
      if (inQuotes && next === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === ',' && !inQuotes) {
      out.push(current.trim());
      current = '';
      continue;
    }

    current += char;
  }

  out.push(current.trim());
  return out;
}

function parseLooseValue(value: string): JsonValue {
  const trimmed = value.trim();
  if (!trimmed) {
    return '';
  }
  if (NUMERIC_PATTERN.test(trimmed)) {
    return Number(trimmed);
  }
  if (trimmed.toLowerCase() === 'true') {
    return true;
  }
  if (trimmed.toLowerCase() === 'false') {
    return false;
  }
  return trimmed;
}

function isLikelyJson(input: string): boolean {
  const trimmed = input.trim();
  return trimmed.startsWith('{') || trimmed.startsWith('[');
}

function parseCsvToTable(input: string): JsonValue {
  const lines = input
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length < 2) {
    throw new Error('CSV must include a header row and at least one data row.');
  }

  const header = parseCsvLine(lines[0]);
  if (header.length < 1) {
    throw new Error('CSV header row is empty.');
  }

  const rows = lines.slice(1).map((line, idx) => {
    const cells = parseCsvLine(line).map((cell) => parseLooseValue(cell));
    if (cells.length !== header.length) {
      throw new Error(
        `CSV row ${idx + 2} has ${cells.length} values, expected ${header.length}.`
      );
    }
    return cells;
  });

  return {
    type: 'table',
    content: {
      caption: 'Pasted table',
      columns: header,
      rows,
    },
  };
}

export function parseEvidenceInput(input: string): JsonValue {
  const trimmed = input.trim();
  if (!trimmed) {
    throw new Error('Evidence is required. Paste CSV or JSON evidence.');
  }

  if (isLikelyJson(trimmed)) {
    try {
      return JSON.parse(trimmed) as JsonValue;
    } catch {
      throw new Error('Evidence looks like JSON but could not be parsed.');
    }
  }

  return parseCsvToTable(trimmed);
}

export function stringifyEvidence(value: JsonValue): string {
  return JSON.stringify(value, null, 2);
}
