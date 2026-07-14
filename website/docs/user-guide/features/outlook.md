# Desktop mail with classic Outlook

Hermes can operate a locally installed desktop mail application through a
provider-neutral tool contract. The first provider uses the Windows COM
automation interface exposed by **classic Outlook**.

The agent can:

- discover configured mailbox stores and folder trees;
- list recent or unread messages;
- read a selected message and attachment metadata;
- create new, reply, reply-all, and forward drafts;
- iteratively revise saved drafts.

There is deliberately no send tool. Drafts remain in the desktop mail
application for human review.

## Why COM

This integration is intended for local or domain-network mail clients whose
desktop applications expose an automation API. Outlook is the development and
testing provider; another corporate client can implement the same
`DesktopMailProvider` interface without changing the agent tools or reasoning
loop.

Microsoft supports the Outlook Object Model in classic Outlook for Windows.
New Outlook for Windows does not expose COM or the Outlook Object Model and is
therefore not compatible with this provider.

## Requirements

- Windows.
- Classic Outlook installed.
- A configured Outlook mail profile.
- Hermes running in the same logged-in interactive Windows session as Outlook.
- `pywin32` installed. It is included automatically in Hermes on Windows.

COM automation is not suitable for a Windows service running outside the
interactive user's session. Run Hermes as the signed-in user, or use a
user-session worker if a gateway process is hosted elsewhere.

## Enable

The plugin and its tool schemas are opt-in:

```bash
hermes plugins enable outlook
hermes tools
```

Enable the `desktop_mail` toolset for the platforms where it should be
available.

Verify the local application:

```bash
hermes outlook status
hermes outlook folders
```

No OAuth application, cloud API, client secret, or new `HERMES_*` environment
variable is required.

## Agent behavior

Ask naturally:

```text
Show the newest unread messages in my corporate mailbox.
Read the message from Alice about the release.
Draft a concise reply agreeing to the proposed time.
Add Priya to CC and make the draft warmer.
```

The model chooses and chains generic tools:

- `mail_client_status`
- `mail_list_folders`
- `mail_list_messages`
- `mail_get_message`
- `mail_create_draft`
- `mail_update_draft`

Messages and folders are addressed by the `entry_id` and `store_id` returned by
the desktop provider. Hermes does not assume account names, domains, folder
paths, or corporate mailbox layouts.

## Provider architecture

The provider contract lives in
`plugins/outlook/providers/base.py`. Outlook-specific COM behavior lives in
`plugins/outlook/providers/outlook_com.py`, including:

- COM apartment initialization for each calling thread;
- MAPI store and folder discovery;
- Outlook `EntryID` plus `StoreID` locators;
- Outlook item conversion into provider-neutral dictionaries;
- draft-only mutation.

A future corporate desktop client should implement `DesktopMailProvider` and
call `register_provider()` from `plugins/outlook/provider.py`. Select it with
non-secret configuration:

```yaml
desktop_mail:
  provider: corporate_client
```

The model-facing schemas should remain unchanged.

## Outlook security prompts

Classic Outlook can display Object Model Guard prompts when an external program
accesses protected address information or attempts to send mail. Hermes does
not modify Trust Center, antivirus, registry, or Group Policy settings to
bypass those protections. Since the plugin does not call `MailItem.Send`, it
also avoids the programmatic-send path.
