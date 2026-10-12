import type { SearchResult } from '../commands/audio.js';

interface CachedSearch {
  query: string;
  results: SearchResult[];
  timestamp: number;
}

const searchCache = new Map<string, CachedSearch>();
const CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutos

export function saveSearch(chatId: string, query: string, results: SearchResult[]): void {
  searchCache.set(chatId, {
    query,
    results,
    timestamp: Date.now()
  });
}

export function getSearch(chatId: string): CachedSearch | null {
  const cached = searchCache.get(chatId);
  if (!cached) return null;
  
  if (Date.now() - cached.timestamp > CACHE_TTL_MS) {
    searchCache.delete(chatId);
    return null;
  }
  
  return cached;
}

export function hasValidSearch(chatId: string): boolean {
  return getSearch(chatId) !== null;
}

// Limpieza periódica
setInterval(() => {
  const now = Date.now();
  for (const [chatId, cached] of searchCache.entries()) {
    if (now - cached.timestamp > CACHE_TTL_MS) {
      searchCache.delete(chatId);
    }
  }
}, 5 * 60 * 1000); // Cada 5 min