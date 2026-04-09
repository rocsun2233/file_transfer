## MODIFIED Requirements

### Requirement: Desktop clients initiate managed transfer tasks
The system SHALL let desktop users select one or more files or folders and send them to a target device as a managed transfer task with a unique task identifier. For desktop-to-desktop transfers, the task MUST be backed by a real transfer session that performs receiver acceptance before file bytes are sent.

#### Scenario: User sends multiple items
- **WHEN** a desktop user selects multiple files and folders for a target device
- **THEN** the system creates one transfer task containing the full item list and target metadata

#### Scenario: Receiver must accept the task
- **WHEN** a desktop sender initiates a managed transfer task to another desktop peer
- **THEN** the task remains pending until the receiver accepts or rejects the transfer

### Requirement: Transfer tasks report progress and outcomes
The system SHALL expose task progress, current state, and completion outcome to the desktop client for every transfer task. The task state model MUST include waiting for acceptance, active transfer, paused or interrupted transfer, failed transfer, and completed transfer.

#### Scenario: Task progress updates during transfer
- **WHEN** a transfer task is actively sending data
- **THEN** the system reports task progress and current transfer state to the desktop UI

#### Scenario: Task completes successfully
- **WHEN** all task items are transferred and validated
- **THEN** the system marks the task as completed and stores the outcome in transfer history

#### Scenario: Task awaits receiver confirmation
- **WHEN** a transfer task has been offered but not yet accepted by the receiver
- **THEN** the system exposes an awaiting acceptance state instead of marking the task in progress

### Requirement: Transfer tasks support interruption recovery
The system SHALL persist enough task state to resume an interrupted transfer instead of restarting the entire task from the beginning.

#### Scenario: Transfer resumes after interruption
- **WHEN** a transfer task is interrupted after partial progress and the peers reconnect
- **THEN** the system resumes the task from persisted progress instead of retransmitting completed segments

### Requirement: Transfer tasks support conflict handling
The system SHALL allow the receiver to resolve destination name conflicts by choosing overwrite, skip, or rename behavior.

#### Scenario: Incoming file conflicts with existing file
- **WHEN** a received file path already exists at the destination
- **THEN** the system offers overwrite, skip, and rename as valid conflict resolution outcomes

### Requirement: Transfer history is retained locally
The system SHALL keep a local history of transfer tasks so users can review recent sends and receives after the original session ends.

#### Scenario: User views recent activity
- **WHEN** a user opens the transfer history view after previous tasks completed or failed
- **THEN** the system shows recent transfer records with status and peer information

## ADDED Requirements

### Requirement: Transfer tasks support retry after recoverable failure
The system SHALL allow a failed or interrupted desktop transfer task to retry using the stored task identity and recoverable transfer state.

#### Scenario: User retries a recoverable transfer
- **WHEN** a transfer task fails after partial progress and the failure is recoverable
- **THEN** the system allows the user or coordinator to restart the task using saved recovery state
