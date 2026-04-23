import { useState } from 'react';
import { ComparisonTable } from './components/ComparisonTable';
import { LoginModal } from './components/LoginModal';
import { OrderListInput } from './components/OrderListInput';
import { ProgressBar } from './components/ProgressBar';
import { ReportView } from './components/ReportView';
import { StatusBadge } from './components/StatusBadge';
import { endpoints } from './api/endpoints';
import { useAuth } from './hooks/useAuth';
import { useProcurement } from './hooks/useProcurement';
import { t } from './i18n/ko';

type View = 'compare' | 'results' | 'report' | 'settings';

const navItems: { id: View; label: string }[] = [
  { id: 'compare', label: t('nav.compare') },
  { id: 'results', label: t('nav.results') },
  { id: 'report', label: t('nav.report') },
  { id: 'settings', label: t('nav.settings') },
];

function maskToken(token: string | null): string {
  if (!token) return '미입력';
  if (token.length <= 12) return '입력됨';
  return `${token.slice(0, 8)}…${token.slice(-4)}`;
}

export function App() {
  const auth = useAuth();
  const procurement = useProcurement();
  const [view, setView] = useState<View>('compare');
  const [backendUrlInput, setBackendUrlInput] = useState(auth.state.api.backendUrl);
  const [tokenInput, setTokenInput] = useState(auth.state.api.accessToken ?? '');
  const [newShopName, setNewShopName] = useState('');

  const startComparison = () => {
    void procurement.startComparison({
      apiOptions: auth.apiOptions,
      shopId: auth.state.api.selectedShopId,
      useApi: auth.canUseApi,
    });
    setView('results');
  };

  const refreshReport = () => {
    if (!auth.canUseApi) return;
    void procurement.refreshReport(auth.apiOptions);
  };

  const renderSettings = () => (
    <section className="panel settings-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">운영 준비</p>
          <h2>{t('settings.title')}</h2>
        </div>
        <span className={`pill ${auth.state.api.status === 'connected' ? 'pill--accent' : ''}`}>
          {auth.state.api.status === 'connected' ? 'API 연결됨' : 'API 연결 필요'}
        </span>
      </div>

      <div className="settings-grid">
        <article className="settings-card">
          <h3>백엔드 API 연결</h3>
          <label>
            백엔드 주소
            <input value={backendUrlInput} onChange={(event) => setBackendUrlInput(event.target.value)} />
          </label>
          <label>
            Bearer access token
            <textarea
              value={tokenInput}
              onChange={(event) => setTokenInput(event.target.value)}
              placeholder="OAuth 콜백에서 받은 access_token을 붙여넣으세요"
              rows={4}
            />
          </label>
          <div className="inline-actions">
            <button
              className="button button--primary"
              onClick={() => void auth.connectApi({ backendUrl: backendUrlInput, accessToken: tokenInput.trim() || null })}
              disabled={auth.state.api.status === 'checking'}
            >
              {auth.state.api.status === 'checking' ? '확인 중...' : '연결 확인'}
            </button>
            <button className="button button--ghost" onClick={() => auth.setApiConfig(backendUrlInput, tokenInput.trim() || null)}>
              설정 저장
            </button>
          </div>
          {auth.state.api.error ? <p className="notice notice--danger">{auth.state.api.error}</p> : null}
        </article>

        <article className="settings-card">
          <h3>테넌트·매장</h3>
          <dl className="settings-list settings-list--compact">
            <div><dt>테넌트</dt><dd>{auth.state.api.tenant?.name ?? '미연결'}</dd></div>
            <div><dt>사용자</dt><dd>{auth.state.api.user?.email ?? '미연결'}</dd></div>
            <div><dt>토큰</dt><dd>{maskToken(auth.state.api.accessToken)}</dd></div>
          </dl>
          <label>
            발주 매장 선택
            <select
              value={auth.state.api.selectedShopId ?? ''}
              onChange={(event) => auth.selectShop(event.target.value ? Number(event.target.value) : null)}
              disabled={!auth.state.api.shops.length}
            >
              <option value="">매장을 선택하세요</option>
              {auth.state.api.shops.map((shop) => (
                <option key={shop.id} value={shop.id}>{shop.name}</option>
              ))}
            </select>
          </label>
          <div className="inline-actions">
            <input
              value={newShopName}
              onChange={(event) => setNewShopName(event.target.value)}
              placeholder="새 매장 이름"
            />
            <button
              className="button"
              onClick={() => {
                void auth.createApiShop(newShopName);
                setNewShopName('');
              }}
            >
              매장 생성
            </button>
          </div>
        </article>
      </div>

      <dl className="settings-list">
        <div><dt>주문 생성</dt><dd>{endpoints.procurement.orders}</dd></div>
        <div><dt>결과 업로드</dt><dd>{endpoints.procurement.orderResults(':orderId')}</dd></div>
        <div><dt>리포트 조회</dt><dd>{endpoints.procurement.reportSummary}</dd></div>
        <div><dt>마켓 세션</dt><dd>쿠키/비밀번호는 서버 미전송 · 로컬 WebView 저장</dd></div>
      </dl>
    </section>
  );

  const renderContent = () => {
    if (view === 'results') {
      return (
        <ComparisonTable
          items={procurement.state.items}
          results={procurement.state.results}
          onRetry={procurement.retryResult}
        />
      );
    }
    if (view === 'report') {
      return (
        <ReportView
          results={procurement.state.results}
          apiReport={procurement.state.apiReport}
          canRefresh={auth.canUseApi}
          onRefreshReport={refreshReport}
        />
      );
    }
    if (view === 'settings') {
      return renderSettings();
    }

    return (
      <div className="compare-layout">
        <OrderListInput
          items={procurement.state.items}
          recentOrders={procurement.recentOrders}
          notice={procurement.state.notice}
          isRunning={procurement.state.isRunning}
          canStart={procurement.canStart}
          onApplyPaste={procurement.applyPaste}
          onAddRow={procurement.addRow}
          onRemoveRow={procurement.removeRow}
          onUpdateRow={procurement.updateRow}
          onCloneRecent={procurement.cloneRecent}
          onStart={startComparison}
        />
        <ProgressBar progress={procurement.state.progress} />
      </div>
    );
  };

  const handleOpenWebview = (platform: 'coupang' | 'naver') => {
    auth.markPlatformLogin(platform);
    auth.closeLoginModal();
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark">
          <span>₩</span>
          <div>
            <strong>lowest-price</strong>
            <small>조달 실가 비교</small>
          </div>
        </div>

        <nav className="nav-list" aria-label="주요 화면">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={view === item.id ? 'is-active' : ''}
              onClick={() => setView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="session-card">
          <span className="session-card__avatar">{auth.state.ownerName.slice(0, 1).toUpperCase()}</span>
          <div>
            <strong>{auth.state.ownerName}</strong>
            <small>{auth.state.tenantName}</small>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="hero-panel">
          <div>
            <span className="pill pill--accent">{t('hero.badge')}</span>
            <h1>{t('hero.primary')}</h1>
            <p>{t('hero.secondary')}</p>
            <div className="hero-actions">
              <button className="button button--primary" onClick={() => setView('compare')}>발주 입력하기</button>
              <button className="button" onClick={() => setView('settings')}>API 연결 설정</button>
              {auth.selectedShop ? <span className="pill">선택 매장: {auth.selectedShop.name}</span> : <span className="pill">매장 미선택</span>}
            </div>
          </div>
          <div className="market-session-panel">
            <div className="market-session-panel__row">
              <span>API 상태</span>
              <span className={`sync-chip sync-chip--${auth.canUseApi ? 'uploaded' : 'local'}`}>
                {auth.canUseApi ? '연결됨' : '로컬 미리보기'}
              </span>
            </div>
            <div className="market-session-panel__row">
              <span>쿠팡 세션</span>
              <StatusBadge status={auth.state.sessions.coupang.status} />
            </div>
            <div className="market-session-panel__row">
              <span>네이버 세션</span>
              <StatusBadge status={auth.state.sessions.naver.status} />
            </div>
            <button className="button button--primary" onClick={auth.openLoginModal}>마켓 로그인 관리</button>
          </div>
        </header>

        {renderContent()}
      </main>

      <LoginModal
        open={auth.state.loginModalOpen}
        onClose={auth.closeLoginModal}
        onOpenWebview={handleOpenWebview}
      />
    </div>
  );
}
