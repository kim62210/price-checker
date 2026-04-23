interface LoginModalProps {
  open: boolean;
  onClose: () => void;
  onOpenWebview: (platform: 'coupang' | 'naver') => void;
}

export function LoginModal({ open, onClose, onOpenWebview }: LoginModalProps) {
  if (!open) return null;

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="login-modal-title" onClick={(event) => event.stopPropagation()}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">세션 보호</p>
            <h2 id="login-modal-title">마켓 로그인 안내</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="닫기">×</button>
        </div>
        <p>
          쿠팡·네이버 로그인은 앱 안의 전용 WebView에서 직접 진행합니다. 쿠키와 세션은 사장님 PC에만 저장되며,
          백엔드로 비밀번호나 쿠키를 전송하지 않습니다.
        </p>
        <div className="privacy-card">
          <strong>안전한 우회 방식</strong>
          <span>서버 크롤링 대신 사장님 본인 로그인 세션에서 직접 조회한 결과만 업로드합니다.</span>
        </div>
        <div className="modal-actions">
          <button className="button button--primary" onClick={() => onOpenWebview('coupang')}>쿠팡 로그인 열기</button>
          <button className="button" onClick={() => onOpenWebview('naver')}>네이버 로그인 열기</button>
          <button className="button button--ghost" onClick={onClose}>닫기</button>
        </div>
      </section>
    </div>
  );
}
