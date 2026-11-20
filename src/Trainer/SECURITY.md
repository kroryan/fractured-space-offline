# Security and provenance

This project targets the local solo server, `spserver.exe`. It reads and modifies that process's memory and executes code inside it for some actions. These operations can trigger heuristic Windows security alerts.

The published scripts do not disable Microsoft Defender or Smart App Control, create scheduled tasks or services, or download remote code. The offline integration runs PowerShell with a process-scoped execution policy; it does not change the system policy.

`data/trainer-debug.log` may be created locally and is excluded from the repository. The original source revision and hashes are recorded in `tools/trainer-lock.json`. Use builds from a source you recognize.
