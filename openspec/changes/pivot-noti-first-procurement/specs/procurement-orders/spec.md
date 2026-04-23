## ADDED Requirements

### Requirement: Procurement order as notification aggregate
The system SHALL treat procurement orders as aggregates that can produce notification events. A procurement order MAY be created or updated without any user-facing UI, and notification delivery MUST be possible from server-side order/result state.

#### Scenario: Create order for notification workflow
- **WHEN** an authenticated tenant creates a procurement order through the API or internal ingestion flow
- **THEN** the order can be used as the aggregate reference for later notification events

#### Scenario: Order completion triggers outbox
- **WHEN** an order reaches a notification-worthy completion state
- **THEN** the system records a notification outbox event referencing the order

### Requirement: UI-independent order lifecycle
The system SHALL NOT require Tauri, React, browser extension, or comparison table interaction for procurement order lifecycle transitions used by notification dispatch.

#### Scenario: No desktop client present
- **WHEN** a procurement result is recorded by an authorized server-side or internal ingestion process
- **THEN** the notification workflow can proceed without a desktop UI session
