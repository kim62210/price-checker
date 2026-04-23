## ADDED Requirements

### Requirement: Procurement result as notification payload source
The system SHALL use procurement result data as the source for notification payloads, including product name, option text, platform/source, landed unit price, savings amount, product URL, and failure state when available.

#### Scenario: Successful result payload
- **WHEN** a procurement result contains ranked lowest-price data
- **THEN** the notification payload includes enough summary information for the recipient to make a purchase decision without opening a comparison UI

#### Scenario: Failed result payload
- **WHEN** a procurement result fails due to login_required, blocked, timeout, parser_failed, or similar collection status
- **THEN** the notification payload includes the failure reason and the next action required

### Requirement: UI rendering is not required for result consumption
The system SHALL expose procurement result data to notification rendering and internal operations without requiring a comparison table UI.

#### Scenario: Generate notification from result
- **WHEN** a completed result is available
- **THEN** the notification service can render an Alimtalk or SMS message from the result data directly
