## ADDED Requirements

### Requirement: Desktop clients initiate managed transfer tasks
The system SHALL let desktop users select one or more files or folders and send them to a target device as a managed transfer task with a unique task identifier.

#### Scenario: User sends multiple items
- **WHEN** a desktop user selects multiple files and folders for a target device
- **THEN** the system creates one transfer task containing the full item list and target metadata

### Requirement: Transfer tasks report progress and outcomes
The system SHALL expose task progress, current state, and completion outcome to the desktop client for every transfer task.

#### Scenario: Task progress updates during transfer
- **WHEN** a transfer task is actively sending data
- **THEN** the system reports task progress and current transfer state to the desktop UI

#### Scenario: Task completes successfully
- **WHEN** all task items are transferred and validated
- **THEN** the system marks the task as completed and stores the outcome in transfer history

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
