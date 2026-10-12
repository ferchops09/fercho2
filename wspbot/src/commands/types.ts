import type { WASocket, WAMessage } from '@whiskeysockets/baileys';

export interface CommandContext {
  msg: WAMessage;
  args: string[];
  sock: WASocket;
  reply: (text: string) => Promise<void>;
  sendSticker: (media: Buffer, options?: { mimetype?: string }) => Promise<void>;
}

export type CommandHandler = (ctx: CommandContext) => Promise<void>;

export interface Command {
  name: string;
  handler: CommandHandler;
  description?: string;
}