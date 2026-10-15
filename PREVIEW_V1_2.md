# Preview v1.2: manual fictional inquiries and editable responses

This change is source code for the existing single-owner preview, not a claim of
successful deployment. Check the exact commit's CI and Render deploy status.

## Visible changes

- Smart Inbox includes Create a fictional inquiry: sender, subject, message and
  a mandatory fictional-data acknowledgement. Sender must end in .test. This is
  an input guard, not automatic personal-data detection; use invented data only.
- Approvals displays the associated task title and an editable response draft.
  Edits remain in memory while changing tabs. Approve saves the edited text and
  decision together. Reloading discards unsaved edits. Reject uses the stored draft.
- Blank drafts cannot be approved. Reviewed drafts are read-only.
- All six navigation tabs are visible in a two-row grid on phone-sized screens.
- A visible banner explains mock processing, no sending and disposable records.

## API safeguards

POST /api/inbox/fictional validates acknowledgement, test sender, field lengths and
nonblank input. An unchanged retry with the same source_id returns the saved
message. Reusing an identifier with changed content returns 409, including a
unique-key race recovery. Creation does not start processing or create a task.

PATCH /api/approvals/{id} accepts expected_draft for optimistic conflict checking.
A conditional database update only decides a still-pending, matching draft. A
competing review is rejected without overwriting the original decision. Task
progression fails closed when an approval record is missing.

No schema migration, authentication change, model provider change, real mail,
CRM integrations, additional hosting resources or paid services are introduced.

## Tests and rollout

24 isolated backend regression cases, nine pure frontend validation tests and
new desktop Chromium/mobile WebKit browser scenarios supplement existing CI.
The browser tests use isolated databases, temporary credentials and localhost
HTTPS, not the hosted owner's session. They cover manual input, validation,
editing, discarding edits, tab switching, conflicting review and saved-text reload.

Auto-deploy remains off. Keep the current hosted preview untouched while testing.
A later manual deployment can erase the disposable SQLite sample records;
confirm that reset is acceptable before deploying. Existing credentials do not
need to be viewed or changed. Persistent storage remains a separate milestone.
