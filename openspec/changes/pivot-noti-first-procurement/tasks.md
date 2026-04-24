## 1. Documentation and Product Direction Cleanup

- [x] 1.1 Update `README.md` to describe the Noti-first product direction and remove Tauri/React as the primary user-facing UI.
- [x] 1.2 Mark `IMPLEMENTATION_PLAN.md` as historical context superseded by `pivot-noti-first-procurement` for product direction.
- [x] 1.3 Update `openspec/changes/tauri-desktop-mvp/README.md` and related docs to classify Tauri assets as internal parser QA/operator tooling only.
- [x] 1.4 Update `openspec/changes/pivot-backend-multi-tenant/*` wording so Tauri/browser extension references are optional ingestion clients, not canonical product surfaces.
- [x] 1.5 Update `openspec/changes/toss-payments-billing/*` wording so billing recovery and payment failure communications are notification-first rather than UI-first.

## 2. Notification Domain Scaffolding

- [x] 2.1 Create `backend/app/notifications/` with `__init__.py`, `models.py`, `schemas.py`, `service.py`, `router.py`, `providers.py`, `dispatcher.py`, and `policy.py`.
- [x] 2.2 Register the notifications router in `backend/app/api/v1/router.py` with tenant-authenticated endpoints.
- [x] 2.3 Extend `backend/app/core/config.py` with Kakao BizMessage, SMS provider, webhook secret, sender profile, retry, and notification quota settings.
- [x] 2.4 Add typed notification error classes or error codes using the existing `backend/app/core/exceptions.py` pattern.

## 3. Persistence and Migrations

- [x] 3.1 Add Alembic migration for `notification_recipients` with tenant_id, normalized phone, optional shop/user references, active status, and audit timestamps.
- [x] 3.2 Add Alembic migration for channel consent records covering transactional Kakao eligibility, Kakao marketing consent, SMS advertising consent, nighttime advertising consent, evidence metadata, granted_at, and revoked_at.
- [x] 3.3 Add Alembic migration for `notification_templates` and `notification_template_versions` with channel, purpose, provider template key, review status, locale, variables, body, fallback body, and effective timestamps.
- [x] 3.4 Add Alembic migration for `notification_outbox_events` with event_type, aggregate reference, payload, status, attempts, next_retry_at, and idempotency_key.
- [x] 3.5 Add Alembic migration for `notification_deliveries`, `notification_delivery_attempts`, `provider_callbacks`, and `notification_dead_letters`.
- [x] 3.6 Add tenant-aware indexes and unique constraints for idempotency, provider_message_id lookup, pending dispatch polling, and cross-tenant isolation.

## 4. Recipient and Consent APIs

- [x] 4.1 Implement recipient create/list/read/update/deactivate service methods with phone normalization and tenant isolation.
- [x] 4.2 Implement consent grant/revoke service methods with channel-specific consent records and evidence metadata.
- [x] 4.3 Implement API routes for recipient and consent management protected by `get_current_tenant`.
- [x] 4.4 Add tests for recipient CRUD, phone normalization, consent grant/revoke, and cross-tenant access blocking.

## 5. Template Management

- [x] 5.1 Implement template catalog and immutable template version models in SQLAlchemy.
- [x] 5.2 Implement template creation and versioning service methods, preserving previous versions on body changes.
- [x] 5.3 Implement message purpose validation so marketing templates cannot use Alimtalk channel.
- [x] 5.4 Implement rendering with required variable validation and delivery-level rendered snapshot output.
- [x] 5.5 Add tests for approved Alimtalk template versions, version preservation, marketing Alimtalk rejection, and missing variable render failure.

## 6. Delivery Creation from Procurement Events

- [x] 6.1 Add a notification event creation hook in `backend/app/procurement/service.py` when procurement results or completion states become notification-worthy.
- [x] 6.2 Implement delivery expansion from outbox event to recipient/channel/template-specific deliveries.
- [x] 6.3 Ensure procurement result payloads include successful lowest-price summaries and failure states such as `login_required`, `blocked`, `timeout`, and `parser_failed`.
- [x] 6.4 Add tests that completed procurement results create transactional Alimtalk deliveries without requiring Tauri/React UI state.
- [x] 6.5 Add tests that missing active recipients skip notification dispatch with an auditable reason.

## 7. Dispatch, Providers, and Fallback

- [x] 7.1 Implement `NotificationProvider` interface with normalized success, retryable failure, and permanent failure result types.
- [x] 7.2 Implement fake provider adapters for tests and local development.
- [x] 7.3 Implement Kakao Alimtalk provider adapter boundary using provider configuration without hardcoding a specific dealer API into domain services.
- [x] 7.4 Implement SMS/LMS provider adapter boundary and fallback body handling.
- [x] 7.5 Implement SMS fallback creation for fallback-eligible Alimtalk failures while enforcing consent and advertising policy.
- [x] 7.6 Add tests for provider success, transient failure, permanent failure, SMS fallback creation, and fallback blocking by consent policy.

## 8. Outbox Worker, Retry, and Idempotency

- [ ] 8.1 Implement transactional outbox persistence in the same DB transaction as the procurement state change.
- [ ] 8.2 Implement dispatcher polling with row-level locking or equivalent concurrency protection so multiple workers do not process the same event.
- [ ] 8.3 Implement retry scheduling with exponential backoff, jitter, max attempts, and next_retry_at.
- [ ] 8.4 Implement delivery idempotency using event type, aggregate id, recipient id, channel, and template version.
- [ ] 8.5 Implement dead-letter transition when max attempts are exhausted.
- [ ] 8.6 Add tests for transaction rollback, two-worker concurrency, worker crash retryability, retryable timeout, max-attempt dead-letter, and duplicate event replay.

## 9. Provider Callback Handling

- [ ] 9.1 Add provider callback endpoint for delivery receipt updates.
- [ ] 9.2 Implement webhook authenticity validation using configured shared secret or provider-specific signature verification.
- [ ] 9.3 Implement callback-to-delivery matching by provider account and provider_message_id under tenant isolation.
- [ ] 9.4 Add tests for valid callback update, invalid signature rejection, unknown provider message id handling, and cross-tenant callback safety.

## 10. Quota, Observability, and Operations

- [ ] 10.1 Extend quota service usage or namespace to support tenant notification send limits separately from search/API quota.
- [ ] 10.2 Add structured logs for event creation, delivery creation, provider attempts, fallback, callbacks, and dead-letter transitions.
- [ ] 10.3 Add operational read APIs for recent deliveries, failed deliveries, and dead-letter inspection under tenant isolation.
- [ ] 10.4 Add tests for notification quota enforcement and operational delivery listing.

## 11. Verification

- [ ] 11.1 Run backend unit tests for notifications, procurement integration, tenancy isolation, auth, quota, and cache.
- [ ] 11.2 Run full backend test suite with `make test`.
- [ ] 11.3 Run OpenSpec validation/status for `pivot-noti-first-procurement` and verify all required artifacts are apply-ready.
- [ ] 11.4 Review git diff to confirm `.openspec/` internals, secrets, and environment files are not included.
