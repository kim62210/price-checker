## ADDED Requirements

### Requirement: Search API is auxiliary to notification workflow
The system SHALL treat search and result ranking APIs as backend support for notification payload generation and internal operations, not as the primary user-facing experience.

#### Scenario: Notification payload requests ranked results
- **WHEN** the notification service needs ranked procurement results for an order
- **THEN** it can use existing tenant-scoped ranking/search logic without requiring a UI request

#### Scenario: User-facing UI unavailable
- **WHEN** no desktop or web UI is deployed
- **THEN** the Noti-first workflow still delivers procurement result summaries through notification channels
