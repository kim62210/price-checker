## ADDED Requirements

### Requirement: Transactional outbox event persistence
The system SHALL persist notification outbox events in the same database transaction as the procurement or billing state change that produced them. Outbox events MUST include event_type, tenant_id, aggregate_type, aggregate_id, payload, idempotency_key, status, attempts, and next_retry_at.

#### Scenario: Procurement result transaction commits
- **WHEN** a procurement result and notification outbox event are created in the same transaction and the transaction commits
- **THEN** both the result and outbox event are visible to dispatcher workers

#### Scenario: Procurement result transaction rolls back
- **WHEN** the transaction rolls back after attempting to create an outbox event
- **THEN** neither the procurement result nor the outbox event is persisted

### Requirement: Durable dispatcher worker
The system SHALL provide a dispatcher worker that claims pending outbox events with row-level locking, creates deliveries, calls provider adapters, and records delivery attempts. Multiple workers MUST NOT process the same event concurrently.

#### Scenario: Two workers poll pending events
- **WHEN** two dispatcher workers poll the same pending outbox queue
- **THEN** row-level locking prevents both workers from processing the same event at the same time

#### Scenario: Worker crash after claim
- **WHEN** a worker crashes before completing an event
- **THEN** the event becomes retryable after its retry visibility window or next_retry_at timestamp

### Requirement: Provider adapter abstraction
The system SHALL isolate external provider calls behind provider adapters for Kakao Alimtalk, Kakao channel/brand message, and SMS/LMS. Adapters MUST return normalized success or failure results.

#### Scenario: Kakao provider accepts message
- **WHEN** the Kakao adapter receives a provider success response
- **THEN** it returns a normalized success result with provider_message_id and raw response metadata

#### Scenario: SMS provider returns retryable error
- **WHEN** the SMS adapter receives a transient provider error
- **THEN** it returns a normalized retryable failure result with error code and retry hint

### Requirement: Retry, idempotency, and dead letter
The system SHALL retry retryable dispatch failures with exponential backoff and jitter up to a configured maximum attempt count. Idempotency keys MUST prevent duplicate deliveries for the same event, recipient, channel, and template version. Exhausted events MUST be moved to dead-letter state.

#### Scenario: Retryable provider timeout
- **WHEN** a provider call times out
- **THEN** the system records an attempt, increments attempt count, schedules next_retry_at, and leaves the delivery retryable

#### Scenario: Max attempts exhausted
- **WHEN** a delivery exceeds its configured maximum retry attempts
- **THEN** the system marks the delivery and outbox event as dead_lettered with the last error

#### Scenario: Duplicate event replay
- **WHEN** the same outbox event is replayed with the same idempotency key
- **THEN** the system does not create a duplicate delivery or second provider call
