import { useMemo, useReducer } from 'react';
import { createShop, fetchCurrentUser, fetchShops, fetchTenant } from '../api/procurement';
import type { ShopRead, TenantRead, UserRead } from '../types/api';
import type { Platform, WorkflowStatus } from '../types/procurement';

interface PlatformSession {
  platform: Platform;
  status: WorkflowStatus;
  lastCheckedAt?: string;
}

interface ApiConnectionState {
  backendUrl: string;
  accessToken: string | null;
  tenant: TenantRead | null;
  user: UserRead | null;
  shops: ShopRead[];
  selectedShopId: number | null;
  status: 'idle' | 'checking' | 'connected' | 'error';
  error: string | null;
}

interface AuthState {
  tenantName: string;
  ownerName: string;
  loginModalOpen: boolean;
  sessions: Record<'coupang' | 'naver', PlatformSession>;
  api: ApiConnectionState;
}

type AuthAction =
  | { type: 'open-login-modal' }
  | { type: 'close-login-modal' }
  | { type: 'mark-platform-login'; platform: 'coupang' | 'naver' }
  | { type: 'mark-platform-required'; platform: 'coupang' | 'naver' }
  | { type: 'set-api-config'; backendUrl?: string; accessToken?: string | null }
  | { type: 'connect-start' }
  | { type: 'connect-success'; tenant: TenantRead; user: UserRead; shops: ShopRead[] }
  | { type: 'connect-error'; error: string }
  | { type: 'select-shop'; shopId: number | null }
  | { type: 'shop-created'; shop: ShopRead };

const STORAGE_KEY = 'lowest-price.api-config.v1';

function loadStoredConfig(): Pick<ApiConnectionState, 'backendUrl' | 'accessToken' | 'selectedShopId'> {
  if (typeof window === 'undefined') {
    return { backendUrl: 'http://localhost:8000', accessToken: null, selectedShopId: null };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { backendUrl: 'http://localhost:8000', accessToken: null, selectedShopId: null };
    const parsed = JSON.parse(raw) as Partial<ApiConnectionState>;
    return {
      backendUrl: typeof parsed.backendUrl === 'string' ? parsed.backendUrl : 'http://localhost:8000',
      accessToken: typeof parsed.accessToken === 'string' ? parsed.accessToken : null,
      selectedShopId: typeof parsed.selectedShopId === 'number' ? parsed.selectedShopId : null,
    };
  } catch {
    return { backendUrl: 'http://localhost:8000', accessToken: null, selectedShopId: null };
  }
}

function persistConfig(api: ApiConnectionState): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      backendUrl: api.backendUrl,
      accessToken: api.accessToken,
      selectedShopId: api.selectedShopId,
    }),
  );
}

const stored = loadStoredConfig();

const initialState: AuthState = {
  tenantName: 'API 미연결',
  ownerName: '사장님',
  loginModalOpen: false,
  sessions: {
    coupang: { platform: 'coupang', status: 'login-required' },
    naver: { platform: 'naver', status: 'login-required' },
  },
  api: {
    backendUrl: stored.backendUrl,
    accessToken: stored.accessToken,
    tenant: null,
    user: null,
    shops: [],
    selectedShopId: stored.selectedShopId,
    status: 'idle',
    error: null,
  },
};

function reducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'open-login-modal':
      return { ...state, loginModalOpen: true };
    case 'close-login-modal':
      return { ...state, loginModalOpen: false };
    case 'mark-platform-login':
      return {
        ...state,
        sessions: {
          ...state.sessions,
          [action.platform]: {
            platform: action.platform,
            status: 'ok',
            lastCheckedAt: new Date().toISOString(),
          },
        },
      };
    case 'mark-platform-required':
      return {
        ...state,
        sessions: {
          ...state.sessions,
          [action.platform]: {
            platform: action.platform,
            status: 'login-required',
            lastCheckedAt: new Date().toISOString(),
          },
        },
      };
    case 'set-api-config': {
      const api = {
        ...state.api,
        backendUrl: action.backendUrl ?? state.api.backendUrl,
        accessToken: action.accessToken !== undefined ? action.accessToken : state.api.accessToken,
        status: 'idle' as const,
        error: null,
      };
      persistConfig(api);
      return { ...state, api };
    }
    case 'connect-start':
      return { ...state, api: { ...state.api, status: 'checking', error: null } };
    case 'connect-success': {
      const selectedShopStillExists = action.shops.some((shop) => shop.id === state.api.selectedShopId);
      const selectedShopId = selectedShopStillExists
        ? state.api.selectedShopId
        : action.shops[0]?.id ?? null;
      const api = {
        ...state.api,
        tenant: action.tenant,
        user: action.user,
        shops: action.shops,
        selectedShopId,
        status: 'connected' as const,
        error: null,
      };
      persistConfig(api);
      return {
        ...state,
        tenantName: action.tenant.name,
        ownerName: action.user.email.split('@')[0] || '사장님',
        api,
      };
    }
    case 'connect-error':
      return { ...state, api: { ...state.api, status: 'error', error: action.error } };
    case 'select-shop': {
      const api = { ...state.api, selectedShopId: action.shopId };
      persistConfig(api);
      return { ...state, api };
    }
    case 'shop-created': {
      const api = {
        ...state.api,
        shops: [action.shop, ...state.api.shops.filter((shop) => shop.id !== action.shop.id)],
        selectedShopId: action.shop.id,
        status: 'connected' as const,
        error: null,
      };
      persistConfig(api);
      return { ...state, api };
    }
  }
}

function getApiOptions(api: ApiConnectionState) {
  return { baseUrl: api.backendUrl, accessToken: api.accessToken };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'API 연결에 실패했습니다.';
}

export function useAuth() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const allPlatformsReady = useMemo(
    () => Object.values(state.sessions).every((session) => session.status === 'ok'),
    [state.sessions],
  );
  const selectedShop = useMemo(
    () => state.api.shops.find((shop) => shop.id === state.api.selectedShopId) ?? null,
    [state.api.selectedShopId, state.api.shops],
  );
  const canUseApi = state.api.status === 'connected' && !!state.api.accessToken && !!state.api.selectedShopId;

  const connectApi = async (config?: { backendUrl?: string; accessToken?: string | null }) => {
    const api = {
      ...state.api,
      backendUrl: config?.backendUrl ?? state.api.backendUrl,
      accessToken: config?.accessToken !== undefined ? config.accessToken : state.api.accessToken,
    };
    if (config) {
      dispatch({ type: 'set-api-config', backendUrl: api.backendUrl, accessToken: api.accessToken });
    }
    if (!api.accessToken) {
      dispatch({ type: 'connect-error', error: 'Bearer access token을 먼저 입력하세요.' });
      return;
    }
    dispatch({ type: 'connect-start' });
    try {
      const options = getApiOptions(api);
      const [tenant, user, shops] = await Promise.all([
        fetchTenant(options),
        fetchCurrentUser(options),
        fetchShops(options),
      ]);
      dispatch({ type: 'connect-success', tenant, user, shops });
    } catch (error) {
      dispatch({ type: 'connect-error', error: errorMessage(error) });
    }
  };

  const createApiShop = async (name: string) => {
    if (!name.trim()) {
      dispatch({ type: 'connect-error', error: '매장 이름을 입력하세요.' });
      return;
    }
    if (!state.api.accessToken) {
      dispatch({ type: 'connect-error', error: 'Bearer access token을 먼저 입력하세요.' });
      return;
    }
    dispatch({ type: 'connect-start' });
    try {
      const shop = await createShop({ name: name.trim() }, getApiOptions(state.api));
      dispatch({ type: 'shop-created', shop });
    } catch (error) {
      dispatch({ type: 'connect-error', error: errorMessage(error) });
    }
  };

  return {
    state,
    allPlatformsReady,
    selectedShop,
    canUseApi,
    apiOptions: getApiOptions(state.api),
    openLoginModal: () => dispatch({ type: 'open-login-modal' }),
    closeLoginModal: () => dispatch({ type: 'close-login-modal' }),
    markPlatformLogin: (platform: 'coupang' | 'naver') => dispatch({ type: 'mark-platform-login', platform }),
    markPlatformRequired: (platform: 'coupang' | 'naver') => dispatch({ type: 'mark-platform-required', platform }),
    setApiConfig: (backendUrl: string, accessToken: string | null) => dispatch({ type: 'set-api-config', backendUrl, accessToken }),
    connectApi,
    createApiShop,
    selectShop: (shopId: number | null) => dispatch({ type: 'select-shop', shopId }),
  };
}
