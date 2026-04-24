import { useState } from 'react';
import type { OrderItem, RecentOrder } from '../types/procurement';
import { t } from '../i18n/ko';
import { formatKrw } from '../utils/format';

interface OrderListInputProps {
  items: OrderItem[];
  recentOrders: RecentOrder[];
  notice: string | null;
  isRunning: boolean;
  canStart: boolean;
  onApplyPaste: (text: string) => void;
  onAddRow: () => void;
  onRemoveRow: (id: string) => void;
  onUpdateRow: (id: string, patch: Partial<OrderItem>) => void;
  onCloneRecent: (id: string) => void;
  onStart: () => void;
}

export function OrderListInput({
  items,
  recentOrders,
  notice,
  isRunning,
  canStart,
  onApplyPaste,
  onAddRow,
  onRemoveRow,
  onUpdateRow,
  onCloneRecent,
  onStart,
}: OrderListInputProps) {
  const [pasteText, setPasteText] = useState('콜라 500ml\t12\n생수 2L\t24');
  const [recentId, setRecentId] = useState(recentOrders[0]?.id ?? '');

  return (
    <section className="panel order-input-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Step 1</p>
          <h2>{t('orders.title')}</h2>
        </div>
        <button className="button button--primary" disabled={!canStart} onClick={onStart}>
          {isRunning ? '비교 중...' : t('orders.start')}
        </button>
      </div>

      <div className="paste-card">
        <label htmlFor="excel-paste">{t('orders.pasteLabel')}</label>
        <textarea
          id="excel-paste"
          value={pasteText}
          onChange={(event) => setPasteText(event.target.value)}
          placeholder={t('orders.pastePlaceholder')}
          rows={4}
        />
        <div className="inline-actions">
          <button className="button" onClick={() => onApplyPaste(pasteText)}>{t('orders.applyPaste')}</button>
          <button className="button button--ghost" onClick={onAddRow}>{t('orders.addRow')}</button>
          <select value={recentId} onChange={(event) => setRecentId(event.target.value)} aria-label="이전 발주 선택">
            {recentOrders.map((order) => (
              <option key={order.id} value={order.id}>{order.label}</option>
            ))}
          </select>
          <button className="button button--ghost" onClick={() => onCloneRecent(recentId)}>{t('orders.cloneRecent')}</button>
        </div>
      </div>

      {notice ? <p className="notice">{notice}</p> : null}

      <div className="editable-table" role="table" aria-label="발주 품목 입력표">
        <div className="editable-table__head" role="row">
          <span>{t('orders.name')}</span>
          <span>{t('orders.qty')}</span>
          <span>{t('orders.unit')}</span>
          <span>{t('orders.target')}</span>
          <span>{t('orders.memo')}</span>
          <span />
        </div>
        {items.map((item) => (
          <div className="editable-table__row" key={item.id} role="row">
            <input
              value={item.name}
              onChange={(event) => onUpdateRow(item.id, { name: event.target.value })}
              placeholder="예: 콜라 500ml"
            />
            <input
              value={item.quantity}
              type="number"
              min={1}
              onChange={(event) => onUpdateRow(item.id, { quantity: Number(event.target.value) })}
            />
            <input
              value={item.unit}
              onChange={(event) => onUpdateRow(item.id, { unit: event.target.value })}
            />
            <input
              value={item.targetUnitPrice ?? ''}
              type="number"
              min={0}
              placeholder="선택"
              onChange={(event) => onUpdateRow(item.id, {
                targetUnitPrice: event.target.value ? Number(event.target.value) : undefined,
              })}
            />
            <input
              value={item.memo ?? ''}
              placeholder={item.targetUnitPrice ? `${formatKrw(item.targetUnitPrice)}/${item.unit} 목표` : '선택'}
              onChange={(event) => onUpdateRow(item.id, { memo: event.target.value })}
            />
            <button className="icon-button" onClick={() => onRemoveRow(item.id)} aria-label={`${item.name || '빈 행'} 삭제`}>×</button>
          </div>
        ))}
      </div>
    </section>
  );
}
