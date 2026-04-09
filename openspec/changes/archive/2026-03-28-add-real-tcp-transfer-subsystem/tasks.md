## 1. Protocol Foundation

- [x] 1.1 Add a transfer protocol module for task offer, accept, reject, chunk, resume, complete, and error messages
- [x] 1.2 Add a resume index structure for per-task, per-file, and per-chunk recovery metadata
- [x] 1.3 Extend persisted task state to cover awaiting acceptance, paused, failed, and retryable transfer states

## 2. TCP Transfer Runtime

- [x] 2.1 Implement a TCP transfer server that accepts transfer sessions from trusted peers
- [x] 2.2 Implement a TCP transfer client that opens transfer sessions and sends task offers before file data
- [x] 2.3 Implement chunked file sending and acknowledged chunk writing to temporary files
- [x] 2.4 Finalize completed files atomically into their destination paths

## 3. Task Coordination

- [x] 3.1 Add a transfer coordinator that converts managed tasks into real transfer sessions
- [x] 3.2 Implement receiver task acceptance and rejection handling
- [x] 3.3 Implement resume negotiation and partial retransmission for interrupted tasks
- [x] 3.4 Implement retry flow for recoverable task failures
- [x] 3.5 Implement overwrite, skip, and rename conflict handling inside the real transfer path

## 4. Validation

- [x] 4.1 Add protocol unit tests for message encoding, decoding, and state transitions
- [x] 4.2 Add loopback integration tests for file, folder, and batch transfer scenarios
- [x] 4.3 Add recovery tests for interrupted transfers, retries, and conflict handling
- [x] 4.4 Add regression tests to confirm trust, history, and web guest access still work after integrating the new transfer subsystem
