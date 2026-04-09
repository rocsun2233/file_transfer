## 1. Desktop State

- [x] 1.1 Add a desktop application state layer that maps devices, tasks, history, and settings into UI-friendly models
- [x] 1.2 Extend core service accessors so the desktop layer can read and update transfer settings, active tasks, and selected device information

## 2. Main Workbench UI

- [x] 2.1 Split the desktop shell into device, task, history, and settings panels
- [x] 2.2 Implement the device panel with device selection, manual device entry, pairing entry point, and refresh behavior
- [x] 2.3 Implement the task panel with active task rows, progress display, status labels, and retry actions
- [x] 2.4 Implement the history panel for completed and failed task browsing
- [x] 2.5 Implement the settings panel for shared directory, default conflict policy, and automatic acceptance behavior

## 3. Transfer Interactions

- [x] 3.1 Add file and folder chooser send flows bound to the currently selected target device
- [x] 3.2 Add a drag-and-drop send entry point or equivalent minimal drop workflow for the selected target device
- [x] 3.3 Add incoming task accept or reject dialogs with task-level conflict policy override
- [x] 3.4 Add explicit error feedback for missing target device, invalid manual address, connection failure, and unwritable shared directory

## 4. Validation

- [x] 4.1 Add desktop state tests for device mapping, task mapping, history ordering, and settings updates
- [x] 4.2 Add UI interaction tests for sending, incoming confirmation, conflict policy updates, and retryable task actions
- [x] 4.3 Add regression tests to confirm desktop UI integration does not break TCP transfer, trust state, or web guest access
