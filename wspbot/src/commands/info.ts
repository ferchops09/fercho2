import type { WAMessage } from '@whiskeysockets/baileys';
import { registerCommand } from './index.js';

const INFO_TEXT = `
*|─────────── INFO ───────────|*

Bot orientado a la multimedia. En desarrollo.
Comandos disponibles:

\`!ping\`: Detalla la latencia con el bot.

\`!s | !sticker\`: Convierte el contenido adjuntado (o bien respondiendo a algun mensaje con imagen/video) a un sticker.

\`!audio [buscar | descargar] [opciones] [titulo | url]\`: Busca o descarga audio de youtube. Opciones:
- \`-r=N|--resultados=N\`: Limita/extiende el numero de resultados mostrados en la busqueda (por defecto 5).
`;

async function infoHandler(ctx: { msg: any; args: string[]; reply: (text: string) => Promise<void> }): Promise<void> {
  const { reply } = ctx;
  await reply(INFO_TEXT);
}

registerCommand('info', infoHandler, 'Muestra la ayuda y comandos disponibles del bot');
