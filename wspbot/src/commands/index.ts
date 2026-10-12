import type { Command, CommandHandler, CommandContext } from './types.js';

const commands = new Map<string, Command>();

export function registerCommand(name: string, handler: CommandHandler, description?: string): void {
  const key = name.toLowerCase();
  commands.set(key, { name: key, handler, description });
}

export async function executeCommand(name: string, ctx: CommandContext): Promise<boolean> {
  const key = name.toLowerCase();
  const command = commands.get(key);

  if (!command) {
    return false;
  }

  try {
    await command.handler(ctx);
  } catch (error) {
    console.error(`Error ejecutando comando "${key}":`, error);
  }

  return true;
}

export function getCommands(): Command[] {
  return Array.from(commands.values());
}

export function hasCommand(name: string): boolean {
  return commands.has(name.toLowerCase());
}