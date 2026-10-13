# Start Portal24 Development With OpenCode

1. Extract this ZIP to `~/projects/portal24-python` (or another **source-only** directory). If already extracted elsewhere, open that folder with OpenCode.
2. Ensure OpenCode is installed and your selected coding model has access to browser/network tools if live investigation is required.
3. Open a terminal:

   ```sh
   cd ~/projects/portal24-python
   opencode
   ```

4. Paste this initial prompt:

   ```text
   Implement the Portal24 Python client described in docs/PROJECT_SPEC.md.
   Follow AGENTS.md and the automatically loaded project instructions.
   Begin with research and verified read-only reconnaissance. Keep
   docs/IMPLEMENTATION_PLAN.md updated as you work, and record sanitized
   findings in docs/REVERSE_ENGINEERING.md. Continue through implementation,
   testing, and safe mirroring rather than stopping after planning.
   Never place credentials or real downloads in this repository.
   Seek my intervention only for secure login/MFA, genuine blockers,
   and explicit approval before any public GitHub publication.
   ```

5. Authenticate when the tool needs it **using a secure, local method**, rather than pasting a password into the agent prompt.
6. Store private mirror files outside the source tree (recommended `~/data/portal24-mirror`).
7. In later sessions, use:

   ```text
   Continue the project based on docs/IMPLEMENTATION_PLAN.md.
   Inspect actual code and test results, then tackle the next unchecked task.
   ```

OpenCode auto-loads `AGENTS.md` in the project and reads `docs/PROJECT_SPEC.md` through the `instructions` entry in `opencode.json`.

This ZIP is a starter brief and does **not** contain a working API client yet.
