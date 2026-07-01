const MOJIBAKE_HINT = /[ÃÂÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/;

function countHan(text: string): number {
  return (text.match(/[\u4e00-\u9fff]/g) || []).length;
}

export function repairPossiblyMojibake(value: string | null | undefined): string {
  if (!value) return "";
  if (!MOJIBAKE_HINT.test(value)) return value;

  const chars = Array.from(value);
  if (!chars.every((char) => char.charCodeAt(0) <= 0xff)) {
    return value;
  }

  try {
    const bytes = Uint8Array.from(chars.map((char) => char.charCodeAt(0)));
    const decoded = new TextDecoder("utf-8", { fatal: false }).decode(bytes).trim();
    if (!decoded || decoded.includes("\uFFFD")) return value;
    if (countHan(decoded) === 0 && countHan(value) === 0 && !/[^\x00-\x7f]/.test(decoded)) {
      return value;
    }
    return decoded;
  } catch {
    return value;
  }
}

export function repairTextList(values: Array<string | null | undefined> | null | undefined): string[] {
  return (values || []).map((value) => repairPossiblyMojibake(value)).filter(Boolean);
}
