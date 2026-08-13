"use strict";

const FIRST_MIN = 48;
const FIRST_TARGET = 190;
const FOLLOWING_TARGET = 330;
const MAX_CHUNKS = 3;

function naturalCut(text, target, minimum = 60) {
  if (text.length <= target) return text.length;
  const windowText = text.slice(0, target + 1);
  const candidates = [
    windowText.lastIndexOf(". "),
    windowText.lastIndexOf("! "),
    windowText.lastIndexOf("? "),
    windowText.lastIndexOf("; "),
    windowText.lastIndexOf(": "),
    windowText.lastIndexOf(", "),
  ];
  const punctuation = Math.max(...candidates);
  if (punctuation >= minimum) return punctuation + 1;
  const space = windowText.lastIndexOf(" ");
  return space >= minimum ? space : target;
}

function splitLongPart(value, target, minimum) {
  const parts = [];
  let remaining = value.trim();
  while (remaining.length > target) {
    const cut = naturalCut(remaining, target, minimum);
    parts.push(remaining.slice(0, cut).trim());
    remaining = remaining.slice(cut).trim();
  }
  if (remaining) parts.push(remaining);
  return parts;
}

export function voiceChunks(value) {
  const clean = String(value || "").replace(/\s+/g, " ").trim();
  if (!clean) return [];
  if (clean.length <= FIRST_TARGET) return [clean];

  const sentences = (clean.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [clean]).map((sentence) => sentence.trim());
  const first = [];
  let firstLength = 0;
  while (sentences.length) {
    const sentence = sentences[0].trim();
    const candidateLength = firstLength + (first.length ? 1 : 0) + sentence.length;
    if (first.length && firstLength >= FIRST_MIN && candidateLength > FIRST_TARGET) break;
    sentences.shift();
    if (candidateLength <= FIRST_TARGET) {
      first.push(sentence);
      firstLength = candidateLength;
      if (firstLength >= FIRST_MIN) break;
      continue;
    }
    const [lead, ...rest] = splitLongPart(sentence, FIRST_TARGET, FIRST_MIN);
    first.push(lead);
    if (rest.length) sentences.unshift(rest.join(" "));
    break;
  }

  const chunks = [first.join(" ")];
  let remainder = sentences.join(" ").trim();
  while (remainder && chunks.length < MAX_CHUNKS) {
    if (chunks.length === MAX_CHUNKS - 1) {
      chunks.push(remainder);
      break;
    }
    const cut = naturalCut(remainder, FOLLOWING_TARGET, 120);
    chunks.push(remainder.slice(0, cut).trim());
    remainder = remainder.slice(cut).trim();
  }
  return chunks.filter(Boolean);
}

export const voicePacingContract = Object.freeze({
  protocol: "jarvis-voice-pacing/1",
  firstTarget: FIRST_TARGET,
  followingTarget: FOLLOWING_TARGET,
  maxChunks: MAX_CHUNKS,
});
