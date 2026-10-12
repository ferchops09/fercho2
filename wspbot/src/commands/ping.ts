import type { WAMessage } from '@whiskeysockets/baileys';
import { registerCommand } from './index.js';

async function pingHandler(ctx: { msg: WAMessage; args: string[]; sock: any; reply: (text: string) => Promise<void> }): Promise<void> {
  const { msg, reply } = ctx;

  const timestamp = Number(msg.messageTimestamp || 0);
  const latency = Date.now() - timestamp * 1000;

  const response = `*Pong!* 🏓\n> Tiempo: ${latency} ms`;

  await reply(response);
}

registerCommand('ping', pingHandler, 'Responde con Pong y la latencia');