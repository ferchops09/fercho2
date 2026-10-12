import type { WAMessage } from '@whiskeysockets/baileys';
import { registerCommand } from './index.js';
import { downloadMediaMessage } from '@whiskeysockets/baileys';
import sharp from 'sharp';
import ffmpeg from 'fluent-ffmpeg';
import { tmpdir } from 'os';
import { join } from 'path';
import { randomBytes } from 'crypto';
import { writeFile, unlink } from 'fs/promises';
import { logger } from '../utils/logger.js';

const reuploadRequest = async (msg: WAMessage): Promise<WAMessage> => msg;

const downloadCtx = {
  reuploadRequest,
  logger: {
    trace: (msg: string) => logger.debug(msg),
    debug: (msg: string) => logger.debug(msg),
    info: (msg: string) => logger.debug(msg),
    warn: (msg: string) => logger.warn(msg),
    error: (msg: string) => logger.error(msg),
    fatal: (msg: string) => logger.error(msg),
    child: () => downloadCtx.logger,
    level: 'silent' as const
  }
};

async function convertImageToWebp(buffer: Buffer): Promise<Buffer> {
  return sharp(buffer)
    .resize(512, 512, {
      fit: 'inside',
      withoutEnlargement: true
    })
    .webp({ quality: 80 })
    .toBuffer();
}

async function convertVideoToWebp(buffer: Buffer): Promise<Buffer> {
  const inputPath = join(tmpdir(), `sticker_in_${randomBytes(6).toString('hex')}.mp4`);
  const outputPath = join(tmpdir(), `sticker_out_${randomBytes(6).toString('hex')}.webp`);

  await writeFile(inputPath, buffer);

  await new Promise<void>((resolve, reject) => {
    ffmpeg(inputPath)
      .inputFormat('mp4')
      .on('error', reject)
      .on('end', () => resolve())
      .addOutputOptions([
        '-vcodec', 'libwebp',
        '-vf', "scale='iw*min(512/iw\\,512/ih)':'ih*min(512/iw\\,512/ih)':force_original_aspect_ratio=decrease,format=rgba,pad=512:512:(ow-iw)/2:(oh-ih)/2:#00000000,fps=8",
        '-loop', '0',
        '-preset', 'default',
        '-quality', '30',
        '-compression_level', '6',
        '-an', '-fps_mode', 'vfr',
        '-t', '3',
        '-fs', '256K'
      ])
      .toFormat('webp')
      .save(outputPath);
  });

  const webpBuffer = await import('fs/promises').then(fs => fs.readFile(outputPath));

  await unlink(inputPath).catch(() => {});
  await unlink(outputPath).catch(() => {});

  return webpBuffer;
}

async function stickerHandler(ctx: { msg: WAMessage; args: string[]; sock: any; reply: (text: string) => Promise<void>; sendSticker: (media: Buffer, options?: { mimetype?: string }) => Promise<void> }): Promise<void> {
  const { msg, sendSticker, sock } = ctx;

  // Obtener el contenido del mensaje (puede ser directo o en mensaje citado)
  let messageContent = msg.message;
  let isImage = !!messageContent?.imageMessage;
  let isVideo = !!messageContent?.videoMessage;

  // Si no hay media directo, verificar si es respuesta a un mensaje con media
  if (!isImage && !isVideo) {
    const quotedMsg = msg.message?.extendedTextMessage?.contextInfo?.quotedMessage;
    if (quotedMsg) {
      messageContent = quotedMsg;
      isImage = !!messageContent?.imageMessage;
      isVideo = !!messageContent?.videoMessage;
    }
  }

  if (!isImage && !isVideo) {
    return;
  }

  try {
    // Determinar el mensaje objetivo para descargar el media
    let targetMsg: WAMessage;
    
    if (messageContent === msg.message) {
      targetMsg = msg;
    } else {
      // Es un mensaje citado - obtener el stanzaId y cargar el mensaje completo
      const stanzaId = msg.message?.extendedTextMessage?.contextInfo?.stanzaId;
      if (stanzaId && sock.loadMessage) {
        targetMsg = await sock.loadMessage(msg.key.remoteJid!, stanzaId);
      } else {
        // Fallback: usar el mensaje citado directamente si tiene la info necesaria
        targetMsg = { ...msg, message: messageContent } as WAMessage;
      }
    }
    
    const mediaBuffer = await downloadMediaMessage(targetMsg, 'buffer', {}, downloadCtx);

    let webpBuffer: Buffer;
    if (isImage) {
      webpBuffer = await convertImageToWebp(mediaBuffer);
    } else {
      webpBuffer = await convertVideoToWebp(mediaBuffer);
    }

    await sendSticker(webpBuffer, {
      mimetype: isImage ? 'image/webp' : 'video/webp'
    });
  } catch (error) {
    logger.error('Error creando sticker', { error: (error as Error).message });
  }
}

registerCommand('sticker', stickerHandler, 'Convierte una imagen/video en sticker');
registerCommand('s', stickerHandler, 'Alias de sticker');