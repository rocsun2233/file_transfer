## ADDED Requirements

### Requirement: Android browser sessions see an explicit access state view
The system SHALL show Android browser users an explicit access state view that indicates whether the session is authorized, awaiting desktop approval, requires a one-time code, or has been denied or expired.

#### Scenario: Android user waits for approval
- **WHEN** an Android browser session opens without an approved guest session
- **THEN** the page shows that access is pending approval instead of showing the main transfer actions immediately

### Requirement: Android browser sessions expose touch-friendly core actions
The system SHALL present upload, download, refresh, and recent-task actions in a touch-friendly layout suitable for Android browser use.

#### Scenario: Android user uploads from mobile browser
- **WHEN** an approved Android browser session opens the page
- **THEN** the page presents a touch-friendly upload entry point that triggers the browser file chooser

### Requirement: Android browser sessions show recent task summaries
The system SHALL show recent task summaries in a mobile-friendly format so Android users can confirm the outcome of recent uploads and downloads.

#### Scenario: Android user checks recent activity
- **WHEN** an approved Android browser session loads the page
- **THEN** the page shows recent task summaries in a mobile-friendly list or card layout

### Requirement: Android browser sessions show mobile-oriented error feedback
The system SHALL show concise, explicit mobile-oriented feedback for permission errors, connection errors, upload failures, and download failures.

#### Scenario: One-time code is invalid
- **WHEN** an Android browser session submits an invalid one-time code
- **THEN** the page shows a clear invalid-code error state rather than a generic error page

### Requirement: Android browser sessions explain support boundaries
The system SHALL explain that Android access currently uses the browser entry point and is not a native Android client.

#### Scenario: Android user reads connection guidance
- **WHEN** an Android browser session views the mobile page
- **THEN** the page includes short guidance stating that Android currently connects through the browser
