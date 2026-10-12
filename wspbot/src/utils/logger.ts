import { createWriteStream, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';

const LOG_DIR = join(process.cwd(), 'logs');
const LOG_FILE = join(LOG_DIR, 'baileys.log');

if (!existsSync(LOG_DIR)) {
  mkdirSync(LOG_DIR, { recursive: true });
}

const fileStream = createWriteStream(LOG_FILE, { flags: 'a' });

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

interface LogEntry {
  level: LogLevel;
  timestamp: string;
  message: string;
  meta?: Record<string, unknown>;
}

function formatLog(entry: LogEntry): string {
  const metaStr = entry.meta ? ` ${JSON.stringify(entry.meta)}` : '';
  return `[${entry.timestamp}] [${entry.level}] ${entry.message}${metaStr}`;
}

function writeToFile(entry: LogEntry): void {
  fileStream.write(formatLog(entry) + '\n');
}

function writeToConsole(entry: LogEntry): void {
  const colors: Record<LogLevel, string> = {
    DEBUG: '\x1b[36m',
    INFO: '\x1b[32m',
    WARN: '\x1b[33m',
    ERROR: '\x1b[31m'
  };
  const reset = '\x1b[0m';
  const color = colors[entry.level] || '';
  console.log(`${color}${formatLog(entry)}${reset}`);
}

function getTimestamp(): string {
  return new Date().toISOString().replace('T', ' ').substring(0, 23);
}

export const logger = {
  debug: (message: string, meta?: Record<string, unknown>) => {
    const entry: LogEntry = { level: 'DEBUG', timestamp: getTimestamp(), message, meta };
    writeToFile(entry);
  },

  info: (message: string, meta?: Record<string, unknown>) => {
    const entry: LogEntry = { level: 'INFO', timestamp: getTimestamp(), message, meta };
    writeToFile(entry);
    writeToConsole(entry);
  },

  warn: (message: string, meta?: Record<string, unknown>) => {
    const entry: LogEntry = { level: 'WARN', timestamp: getTimestamp(), message, meta };
    writeToFile(entry);
    writeToConsole(entry);
  },

  error: (message: string, meta?: Record<string, unknown>) => {
    const entry: LogEntry = { level: 'ERROR', timestamp: getTimestamp(), message, meta };
    writeToFile(entry);
    writeToConsole(entry);
  },

  baileys: (level: string, message: string, meta?: Record<string, unknown>) => {
    const entry: LogEntry = { level: level.toUpperCase() as LogLevel, timestamp: getTimestamp(), message, meta };
    writeToFile(entry);
  }
};

export function getBaileysLogger() {
  return {
    trace: (msg: string, meta?: any) => logger.baileys('DEBUG', msg, meta),
    debug: (msg: string, meta?: any) => logger.baileys('DEBUG', msg, meta),
    info: (msg: string, meta?: any) => logger.baileys('INFO', msg, meta),
    warn: (msg: string, meta?: any) => logger.baileys('WARN', msg, meta),
    error: (msg: string, meta?: any) => logger.baileys('ERROR', msg, meta),
    fatal: (msg: string, meta?: any) => logger.baileys('ERROR', msg, meta),
    child: () => getBaileysLogger(),
    level: 'silent' as const
  };
}