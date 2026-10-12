import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
  WASocket,
  WAMessage,
  downloadMediaMessage,
  proto
} from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import qrcode from 'qrcode-terminal';
import { parseCommand } from './utils/parser.js';
import { executeCommand } from './commands/index.js';
import { logger, getBaileysLogger } from './utils/logger.js';

import './commands/ping.js';
import './commands/sticker.js';
import './commands/audio.js';
import './commands/info.js';

async function connectToWhatsApp(): Promise<void> {
  const { state, saveCreds } = await useMultiFileAuthState('auth_info_baileys');

  const sock = makeWASocket({
    auth: state,
    printQRInTerminal: false,
    browser: ['WSPBot', 'Chrome', '1.0.0'],
    logger: getBaileysLogger()
  });

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      logger.info('Escanea el QR code con WhatsApp');
      qrcode.generate(qr, { small: true });
    }

    if (connection === 'close') {
      const statusCode = (lastDisconnect?.error as Boom)?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      logger.warn('Conexion cerrada', { error: lastDisconnect?.error?.message, reconectando: shouldReconnect });
      if (shouldReconnect) {
        connectToWhatsApp();
      }
    } else if (connection === 'open') {
      logger.info('Conexion al bot: OK');
    }
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('messages.upsert', async (event) => {
    if (event.type !== 'notify') return;

    for (const msg of event.messages) {
      if (msg.key.fromMe) continue;

      const parsed = parseCommand(msg);
      if (!parsed) continue;

      const isGroup = msg.key.remoteJid?.endsWith('@g.us') || false;
      const sender = msg.key.participant || msg.key.remoteJid || 'unknown';

      logger.info('Comando recibido', { 
        comando: parsed.raw, 
        tipo: isGroup ? 'grupo' : 'privado',
        remitente: sender,
        grupo: isGroup ? msg.key.remoteJid : undefined
      });

      const reply = async (text: string) => {
        try {
          await sock.sendMessage(msg.key.remoteJid!, { text }, { quoted: msg });
        } catch (error) {
          logger.error('Error enviando respuesta', { error: (error as Error).message });
        }
      };

      const sendSticker = async (media: Buffer, options?: { mimetype?: string }) => {
        try {
          const isVideo = options?.mimetype === 'video/webp';
          await sock.sendMessage(msg.key.remoteJid!, {
            sticker: media,
            isAnimated: isVideo
          });
        } catch (error) {
          logger.error('Error enviando sticker', { error: (error as Error).message });
        }
      };

      const ctx = {
        msg,
        args: parsed.args,
        sock,
        reply,
        sendSticker
      };

      await executeCommand(parsed.name, ctx);
    }
  });
}

process.on('SIGINT', () => {
  logger.info('Cerrando bot...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  logger.info('Cerrando bot...');
  process.exit(0);
});

connectToWhatsApp().catch((error) => {
  logger.error('Error inicializando cliente', { error: (error as Error).message });
  process.exit(1);
});