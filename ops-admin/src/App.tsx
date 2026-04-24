import { I18nProvider } from './i18n';
import { OpsAdminApp } from './ops-admin/OpsAdminApp';

export function App() {
  return (
    <I18nProvider>
      <OpsAdminApp />
    </I18nProvider>
  );
}
