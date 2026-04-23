## ADDED Requirements

### Requirement: Delivery creation from procurement events
The system SHALL convert eligible procurement order/result events into notification deliveries for each selected recipient, channel, and template. Deliveries MUST reference tenant_id, optional procurement_order_id, recipient_id, template_version_id, channel, purpose, and idempotency_key.

#### Scenario: Procurement result completed
- **WHEN** a procurement result is completed for an order with an active recipient
- **THEN** the system creates a transactional Kakao Alimtalk delivery containing the result summary and procurement order reference

#### Scenario: No active recipient
- **WHEN** a procurement event has no eligible active recipient
- **THEN** the system records the event as skipped and does not enqueue provider dispatch

### Requirement: Delivery status tracking
The system SHALL track delivery lifecycle states including queued, rendering, ready, sending, sent, delivered, failed, blocked, retry_scheduled, and dead_lettered. Status transitions MUST be timestamped.

#### Scenario: Provider send succeeds
- **WHEN** the Kakao or SMS provider accepts a message and returns a provider message id
- **THEN** the system records the delivery as sent with provider_message_id and raw provider response metadata

#### Scenario: Provider send fails permanently
- **WHEN** the provider returns a non-retryable error
- **THEN** the system records the delivery as failed and stores the provider error code and message

### Requirement: SMS fallback delivery
The system SHALL support SMS/LMS fallback for transactional notifications when Kakao delivery fails or is unavailable. Fallback MUST use a separately rendered fallback body and MUST obey SMS consent and legal policy for advertising messages.

#### Scenario: Alimtalk transient failure
- **WHEN** Alimtalk delivery fails with a fallback-eligible provider error
- **THEN** the system creates or schedules an SMS fallback delivery for the same event and recipient

#### Scenario: SMS fallback body too long
- **WHEN** a fallback message exceeds SMS length limits
- **THEN** the system marks it for LMS-capable delivery or fails rendering according to provider capability

### Requirement: Provider callback handling
The system SHALL expose a provider callback endpoint that validates authenticity before updating delivery state. Invalid callbacks MUST be rejected and logged.

#### Scenario: Valid delivery receipt callback
- **WHEN** the provider sends a valid signed callback for a known provider_message_id
- **THEN** the system updates the matching delivery with delivered or failed receipt state

#### Scenario: Invalid callback signature
- **WHEN** a callback fails signature or shared-secret validation
- **THEN** the system returns an unauthorized response and does not mutate delivery state
