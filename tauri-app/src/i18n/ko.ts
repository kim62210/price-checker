import messages from './messages/ko.json';

type MessageKey = keyof typeof messages;

export function t(key: MessageKey): string {
  return messages[key];
}

export { messages };
export type { MessageKey };
