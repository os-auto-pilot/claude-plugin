# Oniesoft Auto-Pilot Claude Plugin

## Project Connection Details

| Key | Value |
|---|---|
| Platform URL | http://localhost:8088 |
| API Key | Oniesoft@123dfgewerrt |
| Project ID | 248af507-c75c-4590-95b8-4145891df8d0 |
| User ID | 15eb541f-2dbe-403f-8191-9e1ad15fc0ef |
| Company ID | 43e4f7c3-1a17-4627-8d95-49fd59076851 |
| Module ID | da43581f-41ff-4d88-b41e-2aff8010d4da |

Use these values for any `oniesoft-test-platform` MCP tool calls that require `token`, `projectId`, or related fields.

## Agent Delegation Rules

When the user asks to analyze an Oniesoft test run (why it failed, compare runs, interpret a stack trace), always delegate to the `oniesoft-test-platform:failure-analyst` subagent via the Agent tool instead of calling MCP tools inline in the main conversation.
