## ADDED Requirements

### Requirement: OAuth supports notification administration
The system SHALL use existing OAuth/JWT authentication to protect notification setup, recipient management, template administration, and delivery status APIs.

#### Scenario: Authenticated tenant manages notification settings
- **WHEN** an authenticated user with a valid tenant JWT updates notification settings
- **THEN** the system applies the change only within that user's tenant

#### Scenario: Unauthenticated notification access
- **WHEN** a request without a valid access token attempts to access notification administration APIs
- **THEN** the system rejects the request
