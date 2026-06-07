const MOJIBAKE_PATTERN = /[ÃÂ�]/;

export function normalizeUtf8Text(value: string | null | undefined): string {
  if (!value) {
    return "";
  }

  if (!MOJIBAKE_PATTERN.test(value)) {
    return value;
  }

  try {
    const bytes = Uint8Array.from(
      Array.from(value, (character) => character.charCodeAt(0)),
    );

    return new TextDecoder("utf-8").decode(bytes);
  } catch {
    return value;
  }
}
