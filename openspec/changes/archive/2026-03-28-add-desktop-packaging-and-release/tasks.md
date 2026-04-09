## 1. Build Setup

- [x] 1.1 Add packaging dependencies and version source files required for desktop builds
- [x] 1.2 Add platform build scripts for Windows, Linux, and macOS using PyInstaller-based packaging
- [x] 1.3 Add a shared build configuration that points packaging at the desktop application entrypoint and required resources

## 2. Release Structure

- [x] 2.1 Add the `dist/` platform output structure for desktop packages
- [x] 2.2 Add the `release/` metadata structure for manifest, changelog, and release README
- [x] 2.3 Generate or copy quick-start documentation and version metadata into the release outputs
- [x] 2.4 Document that Android currently uses browser access only and is not packaged natively

## 3. Verification

- [x] 3.1 Add build-time checks for missing PyInstaller, missing resources, and invalid output paths
- [x] 3.2 Add release verification commands or scripts for startup, main window availability, shared directory creation, and service startup
- [x] 3.3 Add developer documentation describing how to build each platform package and how to validate the outputs
