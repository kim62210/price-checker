const API_PREFIX = '/api/v1';

export const endpoints = {
  auth: {
    kakaoLogin: `${API_PREFIX}/auth/kakao/login`,
    naverLogin: `${API_PREFIX}/auth/naver/login`,
    refresh: `${API_PREFIX}/auth/refresh`,
    logout: `${API_PREFIX}/auth/logout`,
  },
  tenancy: {
    me: `${API_PREFIX}/tenants/me`,
    shops: `${API_PREFIX}/shops`,
    user: `${API_PREFIX}/users/me`,
  },
  procurement: {
    orders: `${API_PREFIX}/procurement/orders`,
    orderResults: (orderId: number | string) => `${API_PREFIX}/procurement/orders/${orderId}/results`,
    reportSummary: `${API_PREFIX}/procurement/reports/summary`,
  },
  search: `${API_PREFIX}/search`,
} as const;
