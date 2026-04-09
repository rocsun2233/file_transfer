## 1. Foundation

- [x] 1.1 Create the desktop shell, local core service, and shared project structure for a cross-platform hybrid file transfer app
- [x] 1.2 Add local persistence for trusted peers, transfer tasks, and transfer history
- [x] 1.3 Define service interfaces for discovery adapters, transfer adapters, and the local web gateway

## 2. Device Discovery And Trust

- [x] 2.1 Implement LAN device advertisement and live device list updates for desktop clients
- [x] 2.2 Add manual device address entry for discovery fallback
- [x] 2.3 Implement first-time approval and one-time pairing code flows for new peers
- [x] 2.4 Persist trusted peer identities and add trust revocation controls

## 3. Managed File Transfer

- [x] 3.1 Implement transfer task creation for files, folders, and batch selections
- [x] 3.2 Implement transfer progress reporting and task state transitions
- [x] 3.3 Implement resumable transfer state persistence for interrupted tasks
- [x] 3.4 Implement overwrite, skip, and rename conflict resolution handling
- [x] 3.5 Implement local transfer history views backed by persisted task records

## 4. Web Guest Access

- [x] 4.1 Implement the local web interface for approved browser-based access
- [x] 4.2 Add access confirmation or one-time code validation for untrusted browser sessions
- [x] 4.3 Implement browser upload, download, and recent-task views within the limited web scope

## 5. Verification

- [x] 5.1 Add unit tests for discovery state, trust state, task state, and conflict handling
- [x] 5.2 Add interface tests covering desktop-to-service and web-to-service contracts
- [x] 5.3 Add cross-platform integration coverage for Windows, Linux, and macOS transfer scenarios
