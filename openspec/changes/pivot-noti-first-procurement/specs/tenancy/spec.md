## ADDED Requirements

### Requirement: Tenant isolation for notification domain
The system SHALL apply tenant isolation to recipients, consents, templates, deliveries, attempts, callbacks, and dead letters. No tenant MUST be able to list, mutate, or infer another tenant's notification data.

#### Scenario: Cross-tenant delivery lookup
- **WHEN** a tenant requests a delivery id belonging to another tenant
- **THEN** the system returns not-found or forbidden without exposing delivery metadata

#### Scenario: Provider callback maps to tenant data
- **WHEN** a provider callback updates a delivery
- **THEN** the system updates only the tenant-owned delivery associated with the provider_message_id and configured provider account
