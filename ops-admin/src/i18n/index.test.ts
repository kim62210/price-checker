import { describe, expect, it } from 'vitest';

import enMessages from './messages/en.json';
import koMessages from './messages/ko.json';
import { getMissingMessageKeys, translate } from './index';

describe('i18n message parity', () => {
  it('keeps English and Korean keys aligned', () => {
    expect(getMissingMessageKeys(koMessages, enMessages)).toEqual([]);
    expect(getMissingMessageKeys(enMessages, koMessages)).toEqual([]);
  });

  it('interpolates message placeholders', () => {
    expect(translate('en', 'common.showingRows', { visible: 3, total: 7 })).toBe('Showing 3 rows of 7');
    expect(translate('ko', 'common.showingRows', { visible: 3, total: 7 })).toBe('3개 표시 / 전체 7개');
  });
});
