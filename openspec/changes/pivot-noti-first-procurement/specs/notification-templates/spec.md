## ADDED Requirements

### Requirement: Template catalog and versions
The system SHALL manage notification templates as stable template codes with one or more immutable versions. Each version MUST include channel, purpose, provider template key, review status, locale, body, fallback body, variables, and effective timestamps.

#### Scenario: Create approved Alimtalk template version
- **WHEN** an operator records a Kakao Alimtalk template approved by the provider
- **THEN** the system stores it as an immutable template version linked to the stable template code

#### Scenario: Preserve previous version
- **WHEN** a template body changes after approval
- **THEN** the system creates a new version and preserves the old version for historical delivery audit

### Requirement: Message purpose enforcement
The system SHALL classify templates by purpose. Alimtalk templates MUST be informational or transactional. Marketing templates MUST target Kakao channel/brand message or SMS marketing channels, not Alimtalk.

#### Scenario: Reject marketing Alimtalk template
- **WHEN** an operator attempts to mark an Alimtalk template as marketing purpose
- **THEN** the system rejects the template version with a policy error

#### Scenario: Allow procurement result Alimtalk template
- **WHEN** a template describes a procurement result, quote completion, order state, or payment recovery notice without promotional content
- **THEN** the system allows the template to be classified as transactional

### Requirement: Rendered message snapshot
The system SHALL store rendered title, body, links, fallback body, variable payload, and template_version_id on each delivery before provider dispatch.

#### Scenario: Template changes after dispatch
- **WHEN** a template version is superseded after a delivery was sent
- **THEN** the historical delivery still exposes the exact rendered content and template version used at send time

#### Scenario: Missing template variable
- **WHEN** rendering a delivery and a required variable is missing
- **THEN** the system marks the delivery as render_failed and does not call the provider
