import type { ComparisonResult, OrderItem, Platform } from '../types/procurement';
import { formatKrw, formatUnitPrice } from '../utils/format';
import { StatusBadge } from './StatusBadge';

interface ComparisonTableProps {
  items: OrderItem[];
  results: ComparisonResult[];
  onRetry: (id: string) => void;
}

const platformLabels: Record<Platform, string> = {
  coupang: '쿠팡',
  naver: '네이버',
  manual: '수동',
};

export function ComparisonTable({ items, results, onRetry }: ComparisonTableProps) {
  if (results.length === 0) {
    return (
      <section className="panel empty-results">
        <p className="eyebrow">Step 2</p>
        <h2>개당 실가 비교표</h2>
        <p>아직 비교 결과가 없습니다. 발주 리스트에서 비교를 시작하세요.</p>
      </section>
    );
  }

  return (
    <section className="panel comparison-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Step 2</p>
          <h2>개당 실가 비교표</h2>
        </div>
        <span className="pill">품목별 그룹 · 실가 오름차순 · API 동기화 표시</span>
      </div>

      <div className="comparison-groups">
        {items.map((item) => {
          const group = results.filter((result) => result.orderItemId === item.id);
          if (!group.length) return null;
          return (
            <article key={item.id} className="comparison-group">
              <div className="comparison-group__heading">
                <div>
                  <h3>{item.name}</h3>
                  <p>{item.quantity}{item.unit} 기준 · 목표 {item.targetUnitPrice ? `${formatKrw(item.targetUnitPrice)}/${item.unit}` : '미설정'}</p>
                </div>
                <span>{group.length}개 옵션</span>
              </div>

              <div className="result-table" role="table" aria-label={`${item.name} 비교 결과`}>
                <div className="result-table__head" role="row">
                  <span>플랫폼</span>
                  <span>옵션 / 셀러</span>
                  <span>가격</span>
                  <span>배송비</span>
                  <span>실수량</span>
                  <span>개당 실가</span>
                  <span>상태</span>
                  <span>API</span>
                </div>
                {group.map((result, index) => (
                  <div className={`result-table__row ${index === 0 && result.unitPrice !== null ? 'is-best' : ''}`} key={result.id} role="row">
                    <span className={`platform-chip platform-chip--${result.platform}`}>{platformLabels[result.platform]}</span>
                    <span>
                      <strong>{result.optionText}</strong>
                      <small>{result.sellerName}</small>
                    </span>
                    <span>{formatKrw(result.listedPrice)}</span>
                    <span>{formatKrw(result.shippingFee)}</span>
                    <span>{result.unitCount ? `${result.unitCount}${result.unit}` : '-'}</span>
                    <span>
                      <strong>{formatUnitPrice(result.unitPrice, result.unit)}</strong>
                      {result.unitPriceConfidence === 'low' ? <small className="warning-copy">추정 · 참고용</small> : null}
                      {result.parserSource?.startsWith('detail') ? <small className="success-copy">상세 페이지 보강</small> : null}
                    </span>
                    <span><StatusBadge status={result.status} /></span>
                    <span className="row-actions">
                      <span className={`sync-chip sync-chip--${result.syncStatus ?? 'local'}`} title={result.syncError}>
                        {result.syncStatus === 'uploaded' ? '업로드' : result.syncStatus === 'failed' ? '보류' : '로컬'}
                      </span>
                      <a href={result.productUrl} target="_blank" rel="noreferrer">열기</a>
                      {result.status !== 'ok' || result.syncStatus === 'failed' ? <button onClick={() => onRetry(result.id)}>재시도</button> : null}
                    </span>
                  </div>
                ))}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
