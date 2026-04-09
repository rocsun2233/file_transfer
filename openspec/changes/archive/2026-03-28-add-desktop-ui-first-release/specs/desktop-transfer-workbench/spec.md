## ADDED Requirements

### Requirement: Desktop application shows a device workbench for transfer targets
The desktop application SHALL show a device workbench that lists discovered devices, manually added devices, trust state, and the currently selected transfer target.

#### Scenario: User selects a transfer target
- **WHEN** the user chooses a device from the workbench
- **THEN** the desktop application marks that device as the current transfer target for subsequent send actions

#### Scenario: User adds a manual device
- **WHEN** the user enters a manual address and confirms it
- **THEN** the desktop application adds that device to the workbench and makes it available for selection

### Requirement: Desktop application shows active task status and actions
The desktop application SHALL show active tasks with status, progress, target peer, item counts, and available actions including retry for recoverable tasks.

#### Scenario: Retryable task shows retry action
- **WHEN** a task enters a retryable state
- **THEN** the desktop application shows a retry action for that task

#### Scenario: In-progress task updates visibly
- **WHEN** an active transfer task reports progress
- **THEN** the desktop application updates the task panel with current progress and state

### Requirement: Desktop application supports file and folder send entry points
The desktop application SHALL let the user start transfers by selecting files, selecting folders, or using a drag-and-drop entry point tied to the currently selected device.

#### Scenario: No target is selected before send
- **WHEN** the user attempts to send files without a selected target device
- **THEN** the desktop application shows a clear error and does not start a transfer

#### Scenario: User sends a folder to selected device
- **WHEN** the user selects a target device and chooses a folder to send
- **THEN** the desktop application starts a managed transfer task for that folder

### Requirement: Desktop application presents receive confirmation
The desktop application SHALL present an accept or reject confirmation dialog for incoming transfer tasks and SHALL allow the user to override the default conflict strategy for that task.

#### Scenario: User accepts incoming task with conflict strategy
- **WHEN** an incoming transfer task arrives
- **THEN** the desktop application shows sender information, item summary, and conflict strategy controls before the user accepts or rejects

### Requirement: Desktop application separates active tasks from history
The desktop application SHALL show recent completed or failed tasks in a separate history area distinct from the active task panel.

#### Scenario: User reviews previous activity
- **WHEN** the user opens the history area after earlier tasks have completed or failed
- **THEN** the desktop application shows historical task entries without mixing them into the active task controls

### Requirement: Desktop application exposes essential transfer settings
The desktop application SHALL expose essential settings including shared directory, default conflict policy, and automatic acceptance behavior for trusted peers.

#### Scenario: User changes default conflict policy
- **WHEN** the user updates the default conflict policy in settings
- **THEN** the desktop application persists the new default and uses it for subsequent incoming task confirmations
