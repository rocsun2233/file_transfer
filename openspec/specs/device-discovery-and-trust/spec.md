## ADDED Requirements

### Requirement: System discovers LAN devices automatically
The system SHALL advertise each running device on the local network and SHALL maintain a live device list for the desktop client. The system MUST also allow users to connect by manually entering a device address when automatic discovery is unavailable.

#### Scenario: Nearby device becomes visible
- **WHEN** two devices are running on the same LAN and discovery traffic is permitted
- **THEN** each desktop client shows the other device in its available device list

#### Scenario: Automatic discovery is unavailable
- **WHEN** a user cannot see a target device in the discovered device list
- **THEN** the system allows the user to enter a device address manually and attempt a connection

#### Scenario: Manual connection uses the peer transfer endpoint
- **WHEN** a user manually adds a peer by address
- **THEN** the system stores and uses that peer's LAN-reachable transfer endpoint instead of rewriting the connection to localhost

### Requirement: First-time connections require trust establishment
The system SHALL require first-time connections between two devices to be approved by the receiving side through an explicit confirmation or a one-time pairing code before any transfer session is accepted.

#### Scenario: Receiving device confirms a new peer
- **WHEN** a sender initiates a connection to a device that has no stored trust relationship
- **THEN** the receiver prompts for approval before the connection becomes trusted

#### Scenario: Pairing code is used for first trust
- **WHEN** a receiver requires a one-time pairing code for a new peer
- **THEN** the connection is trusted only after the sender provides the correct code

### Requirement: Trusted peers persist across sessions
The system SHALL persist trust relationships locally so that a previously paired peer can reconnect without repeating first-time approval, until the user revokes trust.

#### Scenario: Returning peer reconnects
- **WHEN** a previously trusted device reconnects later from the same persisted identity
- **THEN** the system allows the connection without repeating first-time pairing

#### Scenario: User revokes trust
- **WHEN** a user removes a trusted device from the trust list
- **THEN** the next connection from that device is treated as a first-time connection
