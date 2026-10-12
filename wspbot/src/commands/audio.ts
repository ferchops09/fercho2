import type { WAMessage } from '@whiskeysockets/baileys';
import { registerCommand } from './index.js';
import { saveSearch, getSearch, hasValidSearch } from '../utils/searchCache.js';
import { readFile, readFileSync, statSync, unlinkSync, renameSync } from 'fs';
import { promisify } from 'util';
import { execFile } from 'child_process';

const DLAPI_BASE = process.env.DLAPI_URL || 'http://localhost:7421';

const execFileAsync = promisify(execFile);

export interface SearchResult {
  title: string;
  author: string;
  view_count: number;
  views_formatted: string;
  duration: number;
  duration_formatted: string;
  video_id: string;
  url: string;
  thumbnail: string;
}

interface SearchResponse {
  status: string;
  query?: string;
  count?: number;
  results?: SearchResult[];
  message?: string;
}

interface DownloadResponse {
  status: string;
  file_path?: string;
  file_id?: string;
  metadata?: {
    title: string;
    artist: string;
    duration_ms: number;
    duration_formatted: string;
    thumbnail_url: string;
    filesize_bytes: number;
    filesize_formatted: string;
    video_id: string;
    views_formatted?: string;
  };
  message?: string;
}

async function searchYouTube(query: string, limit = 10): Promise<SearchResult[]> {
  const url = `${DLAPI_BASE}/search?q=${encodeURIComponent(query)}&limit=${limit}`;
  const res = await fetch(url);

  if (!res.ok) {
    throw new Error(`Error en búsqueda: ${res.status}`);
  }

  const data: SearchResponse = await res.json();

  if (data.status !== 'ok') {
    throw new Error(data.message || 'Error en búsqueda');
  }

  return data.results ?? [];
}

async function downloadAudio(videoId: string): Promise<{ filePath: string; metadata: DownloadResponse['metadata'] }> {
  const url = `${DLAPI_BASE}/download?url=https://www.youtube.com/watch?v=${videoId}`;
  const res = await fetch(url);

  if (!res.ok) {
    throw new Error(`Error en descarga: ${res.status}`);
  }

  const data: DownloadResponse = await res.json();

  if (data.status !== 'ok' || !data.file_path || !data.metadata) {
    throw new Error(data.message || 'Error en descarga');
  }

  return { filePath: data.file_path, metadata: data.metadata };
}

function formatResults(query: string, results: SearchResult[], limit: number): string {
  if (results.length === 0) {
    return `*Resultados para:* _${query}_\n\nNo se encontraron resultados.`;
  }

  const totalResults = results.length;
  const displayLimit = Math.min(limit, totalResults);
  let output = `*Resultados para:* _${query}_ (${displayLimit}/${totalResults})\n\n`;

  results.slice(0, displayLimit).forEach((result, index) => {
    output += `${index + 1}- \`${result.title}\`\n`;
    output += `> Autor: ${result.author}\n`;
    output += `> Vistas: ${result.views_formatted}\n`;
    output += `> Duración: ${result.duration_formatted}\n\n`;
  });

  return output.trim();
}

interface ParsedAudioArgs {
  subcommand: string;
  query: string;
  limit: number;
}

function parseAudioArgs(args: string[]): ParsedAudioArgs {
  let limit = 5;
  let subcommand = '';
  let query = '';

  if (args.length === 0) {
    return { subcommand: '', query: '', limit };
  }

  subcommand = args[0].toLowerCase();

  // Parse remaining args for flags
  const remaining = args.slice(1);
  const queryParts: string[] = [];

  for (const arg of remaining) {
    if (arg.startsWith('--resultados=')) {
      const val = parseInt(arg.split('=')[1], 10);
      if (!isNaN(val) && val > 0) limit = Math.min(val, 20);
    } else if (arg.startsWith('-r=')) {
      const val = parseInt(arg.split('=')[1], 10);
      if (!isNaN(val) && val > 0) limit = Math.min(val, 20);
    } else {
      queryParts.push(arg);
    }
  }

  query = queryParts.join(' ');

  return { subcommand, query, limit };
}

function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function extractVideoId(input: string): string | null {
  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/|music\.youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})/,
    /youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/,
    /youtube\.com\/v\/([a-zA-Z0-9_-]{11})/,
  ];
  
  for (const pattern of patterns) {
    const match = input.match(pattern);
    if (match && match[1]) {
      return match[1];
    }
  }
  return null;
}

const ERROR_MSG = '📛 Error interno. Intente más tarde.';

async function audioHandler(ctx: {
  msg: WAMessage;
  args: string[];
  reply: (text: string) => Promise<void>;
  sock: any;
  sendSticker: any;
}): Promise<void> {
  const { msg, args, reply, sock } = ctx;
  const chatId = msg.key.remoteJid || '';

  if (args.length === 0) {
    await reply(`📛 *Comando inválido.*\n> Use: _*!info*_ para mas detalles.`);
    return;
  }

  const { subcommand, query, limit } = parseAudioArgs(args);

  if (subcommand === 'buscar') {
    if (!query) {
      await reply(`📛 *Falta el término de búsqueda.*\n> Use: _*!info*_ para mas detalles.`);
      return;
    }

    try {
      const results = await searchYouTube(query, limit);
      // Guardar en cache
      saveSearch(msg.key.remoteJid || '', query, results);
      const response = formatResults(query, results ?? [], limit);
      await reply(response);
    } catch (error) {
      console.error('Error en comando audio buscar:', error);
      await reply(ERROR_MSG);
    }
    return;
  }

  if (subcommand === 'descargar') {
    if (!query) {
      await reply(`📛 *Falta el término o índice.*\n> Use: _*!info*_ para mas detalles.`);
      return;
    }

    try {
      // Verificar si es un número (índice de búsqueda previa)
      const index = parseInt(query, 10);

      if (!isNaN(index)) {
        // USO 2: Descargar por índice de búsqueda previa
        if (!hasValidSearch(chatId)) {
          await reply(`📛 *No hay búsqueda previa en este chat.*\n> Use: _*!info*_ para mas detalles.`);
          return;
        }

        const cached = getSearch(chatId);
        if (!cached || index < 1 || index > cached.results.length) {
          await reply(`📛 *Índice inválido.* La búsqueda previa tiene ${cached?.results.length || 0} resultados (1-${cached?.results.length || 0}).\n> Use: _*!info*_ para mas detalles.`);
          return;
        }

        const videoId = cached.results[index - 1].video_id;
        await downloadAndSend(videoId, ctx, msg);
        return;
      }

      // Verificar si es una URL de YouTube
      const videoIdFromUrl = extractVideoId(query);
      let videoId: string;
      let shouldCache = true;

      if (videoIdFromUrl) {
        // USO 3: URL directa de YouTube - no cachear
        videoId = videoIdFromUrl;
        shouldCache = false;
      } else {
        // USO 1: Buscar y descargar primer resultado
        const results = await searchYouTube(query, 1);
        if (results.length === 0) {
          await reply(`📛 *No se encontraron resultados para:* ${query}`);
          return;
        }

        videoId = results[0].video_id;

        // Guardar en cache
        saveSearch(chatId, query, results);
      }

      await downloadAndSend(videoId, ctx, msg);

    } catch (error) {
      console.error('Error en comando audio descargar:', error);
      await reply(ERROR_MSG);
    }
    return;
  }

  await reply(`📛 *Subcomando desconocido:* ${subcommand}\n> Use: _*!info*_ para mas detalles.`);
}

async function cleanAudioFile(inputPath: string): Promise<string> {
  const outputPath = inputPath.replace('.m4a', '.clean.m4a');

  // Usar ffmpeg para copiar solo el stream de audio, eliminando video (cover art)
  await execFileAsync('ffmpeg', [
    '-y',
    '-i', inputPath,
    '-map', '0:a:0',  // Solo primer stream de audio
    '-c:a', 'copy',   // Copiar sin re-encodear
    '-movflags', '+faststart',
    outputPath
  ]);

  // Reemplazar archivo original con el limpio
  renameSync(outputPath, inputPath);
  return inputPath;
}

async function downloadAndSend(
  videoId: string,
  ctx: { reply: (text: string) => Promise<void>; sock: any },
  msg: WAMessage
): Promise<void> {
  const { reply, sock } = ctx;
  const chatId = msg.key.remoteJid || '';
  let filePath: string | null = null;

  try {
    // Descargar audio
    const result = await downloadAudio(videoId);
    if (!result.metadata) {
      throw new Error('Metadatos no disponibles');
    }
    filePath = result.filePath;
    const { metadata } = result;

    // Validar duración (máx 20 min = 1200000 ms)
    if (metadata.duration_ms > 20 * 60 * 1000) {
      await reply(`📛 *El audio excede el límite de 20 minutos* (duración: ${formatDuration(metadata.duration_ms)})\n> Use: _*!info*_ para mas detalles.`);
      return;
    }

    // Verificar tamaño del archivo
    const stats = statSync(filePath);
    const maxSize = 16 * 1024 * 1024; // 16MB límite para audio nativo

    // Usar vistas desde metadata si está disponible
    const viewsFormatted = metadata.views_formatted || 'N/A';

    // Limpiar archivo: remover video stream (cover art) que causa problemas en WhatsApp
    filePath = await cleanAudioFile(filePath);

    // Re-leer stats después de limpiar
    const cleanStats = statSync(filePath);

    // Enviar mensaje 1: Thumbnail + info
    const caption = `\`Título:\` ${metadata.title}\n\`Autor:\` ${metadata.artist}\n\`Vistas:\` ${viewsFormatted}\n\`Duración:\` ${metadata.duration_formatted}`;
    
    await sock.sendMessage(chatId, {
      image: { url: metadata.thumbnail_url },
      caption
    }, { quoted: msg });

    // Enviar mensaje 2: Audio
    const audioBuffer = readFileSync(filePath);
    
    if (cleanStats.size <= maxSize) {
      // Audio nativo reproducible - M4A es contenedor MP4 con audio AAC
      await sock.sendMessage(chatId, {
        audio: audioBuffer,
        mimetype: 'audio/mp4',
        fileName: `${metadata.title}.m4a`,
        ptt: false
      }, { quoted: msg });
    } else {
      // Documento si excede 16MB
      await sock.sendMessage(chatId, {
        document: audioBuffer,
        mimetype: 'audio/mp4',
        fileName: `${metadata.title}.m4a`
      }, { quoted: msg });
    }

  } catch (error) {
    console.error('Error en downloadAndSend:', error);
    await reply(ERROR_MSG);
  } finally {
    // Eliminar archivo temporal después de enviar
    if (filePath) {
      try {
        unlinkSync(filePath);
      } catch {
        // Ignorar errores de limpieza
      }
    }
  }
}

registerCommand('audio', audioHandler, 'Busca y descarga audio de YouTube (subcomandos: buscar, descargar)');
