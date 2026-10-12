import type { WAMessage } from '@whiskeysockets/baileys';

export interface ParsedCommand {
  name: string;
  args: string[];
  raw: string;
}

export function parseCommand(message: WAMessage, prefix = '!'): ParsedCommand | null {
  const text = message.message?.conversation
    || message.message?.extendedTextMessage?.text
    || message.message?.imageMessage?.caption
    || message.message?.videoMessage?.caption
    || message.message?.documentMessage?.caption
    || '';

  const trimmed = text.trim();

  if (!trimmed || !trimmed.startsWith(prefix)) {
    return null;
  }

  const withoutPrefix = trimmed.slice(prefix.length).trim();

  if (!withoutPrefix) {
    return null;
  }

  const parts = withoutPrefix.split(/\s+/);
  const name = parts[0].toLowerCase();
  const args = parts.slice(1);

  return { name, args, raw: trimmed };
}