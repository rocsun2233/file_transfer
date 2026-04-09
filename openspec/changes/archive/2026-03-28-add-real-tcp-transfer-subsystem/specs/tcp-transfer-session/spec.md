## ADDED Requirements

### Requirement: Desktop peers establish a TCP transfer session before sending file data
The system SHALL establish a TCP transfer session between two trusted desktop peers before sending file data for a managed transfer task.

#### Scenario: Sender opens a transfer session
- **WHEN** a user starts a managed transfer task to a trusted desktop peer
- **THEN** the sender opens a TCP session and sends a task offer before any file bytes are transmitted

### Requirement: Transfer sessions require receiver task acceptance
The system SHALL require the receiving peer to accept or reject a proposed transfer task before file chunks are written.

#### Scenario: Receiver accepts a proposed task
- **WHEN** the receiver approves a task offer for a trusted peer
- **THEN** the system returns an acceptance message and allows chunk transmission to begin

#### Scenario: Receiver rejects a proposed task
- **WHEN** the receiver declines a task offer
- **THEN** the system rejects the transfer session without writing task file data

### Requirement: Transfer sessions use chunk acknowledgements
The system SHALL send file data as discrete chunks and SHALL require the receiver to acknowledge chunk completion before the sender advances through the session.

#### Scenario: Receiver acknowledges a chunk
- **WHEN** the receiver writes a chunk successfully
- **THEN** the system records that chunk as completed and returns an acknowledgement to the sender

### Requirement: Transfer sessions support resume negotiation
The system SHALL let reconnecting peers negotiate which files and chunks remain incomplete for a previously interrupted task.

#### Scenario: Interrupted task resumes
- **WHEN** peers reconnect for a task with stored resume state
- **THEN** the receiver returns incomplete file or chunk information and the sender retransmits only missing data

### Requirement: Completed files are finalized atomically
The system SHALL write incoming file data to a temporary location and SHALL move the file into its final destination only after the file is fully received and validated.

#### Scenario: File transfer finishes successfully
- **WHEN** the receiver has all expected data for a file and validation succeeds
- **THEN** the system atomically finalizes the file into its destination path
