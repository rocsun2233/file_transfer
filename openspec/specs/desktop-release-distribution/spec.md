## ADDED Requirements

### Requirement: Desktop builds produce platform-specific distribution directories
The system SHALL define platform-specific distribution directories for Windows, Linux, and macOS so each desktop build has a predictable output location.

#### Scenario: Linux build output is organized
- **WHEN** the Linux build workflow completes successfully
- **THEN** the distribution artifacts are placed under a Linux-specific distribution directory

#### Scenario: Windows build output is organized
- **WHEN** the Windows build workflow completes successfully
- **THEN** the distribution artifacts are placed under a Windows-specific distribution directory

### Requirement: Desktop release workflow uses PyInstaller-based build steps
The system SHALL provide build steps that package the desktop application with `PyInstaller` in a form suitable for direct distribution on each supported desktop platform.

#### Scenario: Build workflow prepares a desktop package
- **WHEN** a platform build script runs in a valid environment
- **THEN** the workflow invokes the PyInstaller-based packaging step for that platform

### Requirement: Release metadata and quick-start documentation are published with desktop artifacts
The system SHALL provide release metadata and quick-start documentation that describe version, supported platforms, startup instructions, and known limitations for the desktop release.

#### Scenario: User inspects release contents
- **WHEN** a user opens the release directory after a build
- **THEN** the release contents include version information and quick-start documentation

### Requirement: Release documentation states Android support boundary
The system SHALL explicitly state that Android is currently supported through browser access only and that no Android native package is part of this release workflow.

#### Scenario: User checks Android support status
- **WHEN** a user reads the release documentation
- **THEN** the documentation explains that Android currently connects through the browser and is not packaged as a native client

### Requirement: Desktop release workflow defines artifact-level verification steps
The system SHALL define verification steps for packaged desktop artifacts, including application startup, main window availability, shared directory creation, and service startup checks.

#### Scenario: Packaged artifact is validated
- **WHEN** a platform package is prepared for distribution
- **THEN** the release workflow includes explicit checks for startup, UI availability, shared directory creation, and service initialization
