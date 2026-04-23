## ADDED Requirements

### Requirement: Tenant-scoped notification recipients
The system SHALL manage notification recipients as tenant-scoped records independent from `users` and `shops`. Each recipient MUST store normalized contact data, display name, optional shop/user references, active status, and audit timestamps.

#### Scenario: Create recipient for current tenant
- **WHEN** an authenticated tenant user creates a recipient with a valid Korean mobile number
- **THEN** the system stores the recipient under the current tenant and normalizes the phone number before persistence

#### Scenario: Block cross-tenant recipient access
- **WHEN** a tenant user requests a recipient belonging to another tenant
- **THEN** the system returns a not-found or forbidden response without leaking recipient details

### Requirement: Channel-specific consent state
The system SHALL track consent independently for transactional Kakao notices, Kakao marketing messages, SMS marketing messages, and nighttime advertising messages. Consent records MUST include consent source, granted_at, revoked_at, and evidence metadata.

#### Scenario: Transactional notice does not imply marketing consent
- **WHEN** a recipient has transactional Kakao notice eligibility but no Kakao marketing consent
- **THEN** the system allows transactional Alimtalk delivery and blocks marketing channel/brand message delivery

#### Scenario: Revoke marketing consent
- **WHEN** a recipient revokes Kakao marketing consent
- **THEN** future marketing notification dispatches to Kakao channel/brand message are blocked for that recipient

### Requirement: Consent gate before dispatch
The system SHALL evaluate recipient consent before creating channel delivery attempts. Dispatch MUST fail closed when required consent or eligibility is absent.

#### Scenario: Block advertising SMS without consent
- **WHEN** a marketing notification requests SMS fallback for a recipient without SMS advertising consent
- **THEN** the system marks the fallback delivery as blocked by consent policy and does not call the SMS provider

#### Scenario: Block nighttime advertising
- **WHEN** a marketing notification is scheduled outside the allowed advertising window and the recipient lacks nighttime advertising consent
- **THEN** the system defers or blocks dispatch according to policy and records the reason
