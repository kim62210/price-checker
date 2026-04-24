import { translate } from './index';
import koMessages from './messages/ko.json';

import type { MessageKey, MessageValues } from './index';

export function t(key: MessageKey, values?: MessageValues): string {
  return translate('ko', key, values);
}

export const messages = koMessages;

export type { MessageKey };
