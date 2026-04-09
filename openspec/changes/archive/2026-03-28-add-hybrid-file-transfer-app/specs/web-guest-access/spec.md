## ADDED Requirements

### Requirement: Each device exposes a local web access point
The system SHALL expose a local web interface on each running device so that another device can access limited file transfer functions through a browser without installing the desktop client.

#### Scenario: Browser opens local web interface
- **WHEN** a user opens the published device address in a browser
- **THEN** the system serves a web interface for that target device

### Requirement: Untrusted browser sessions are restricted
The system SHALL require an access confirmation or one-time code before an untrusted browser session can upload or download files.

#### Scenario: Unknown browser requests access
- **WHEN** a browser visits a device without an existing trusted relationship
- **THEN** the system blocks file operations until the browser session is approved or validated with a one-time code

### Requirement: Browser access supports limited transfer operations
The system SHALL allow approved browser sessions to browse permitted content, upload files, download files, and view recent transfer tasks, but SHALL NOT require browser clients to manage advanced transfer orchestration.

#### Scenario: Approved browser uploads a file
- **WHEN** a browser session has been approved and the user submits a file upload
- **THEN** the system accepts the upload into the permitted destination scope

#### Scenario: Browser downloads a shared item
- **WHEN** a browser session has been approved and the user requests a downloadable item
- **THEN** the system provides the requested item for download

### Requirement: Browser access remains secondary to desktop management
The system SHALL reserve advanced operations such as drag-and-drop desktop sending, device trust management, and complex task controls for the desktop client.

#### Scenario: User needs advanced controls
- **WHEN** a user attempts an operation that requires device trust management or complex task control
- **THEN** the system directs that operation to the desktop client instead of exposing it fully in the browser UI
