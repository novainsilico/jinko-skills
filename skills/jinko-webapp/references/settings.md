# Raw file settings

The raw file settings say how Jinkō displays one raw file, and what its page
can do. "Config" is one of them: the data that Jinkō gives to an HTML page.

## SDK functions

- `raw_file.settings()` returns the stored settings as a dictionary. It holds
  only the keys that were set; an absent key has its default. It is empty
  when nothing was set.
- `raw_file.update_settings({...})` sets the given keys and keeps the others.
- `raw_file.reset_settings()` removes every stored setting, so that each key
  has its default.

The settings do not depend on the version of the file: a new version keeps
them. The SDK sends the keys as given and does not check them, so use the
exact keys of this page. Ignore the `_version` key of the result: the SDK
writes it.

## Which keys apply

Jinkō reads the settings by content type. Push an HTML file with
`content_type="text/html"` and a bundle with
`content_type="application/zip"`, so that the keys below apply.

| Form | Keys that apply |
|---|---|
| Embedded application (zip) | `rendering`, "can do" keys, permission keys |
| HTML raw file | "can do" keys, permission keys, `config` |
| Any other file | None |

## Display of a zip archive

| Key | Values | Default | Effect |
|---|---|---|---|
| `rendering` | `"Default"`, `"Application"` | `"Default"` | `Default` shows a card with a download button. `Application` runs the archive as an embedded application. |

With `Application`, Jinkō checks the archive first. An archive with no valid
`manifest.json` shows an "invalid application" message.

## What the page can do

Each key is a boolean. An HTML raw file starts with all of them off. An
embedded application starts with `sandbox_allow_scripts` and
`sandbox_allow_same_origin` on, and the others off.

| Key | Default, HTML | Default, application | Lets the page |
|---|---|---|---|
| `sandbox_allow_scripts` | `false` | `true` | Run JavaScript. |
| `sandbox_allow_same_origin` | `false` | `true` | Keep its own origin: storage, cookies, and requests to its own files. |
| `sandbox_allow_forms` | `false` | `false` | Submit forms. |
| `sandbox_allow_modals` | `false` | `false` | Open `alert`, `confirm`, `prompt`, and print dialogs. |
| `sandbox_allow_popups` | `false` | `false` | Open new windows or tabs, links with `target="_blank"` included. |
| `sandbox_allow_popups_to_escape_sandbox` | `false` | `false` | Open those windows without the limits of the page. |
| `sandbox_allow_downloads` | `false` | `false` | Start a file download. |
| `sandbox_allow_pointer_lock` | `false` | `false` | Capture the mouse pointer. |
| `sandbox_allow_top_navigation_by_user_activation` | `false` | `false` | Replace the Jinkō page with another page after a click. |

Turn a key on only when the app has a feature that needs it, and say it in the
report. Examples: an "Export CSV" button needs `sandbox_allow_downloads`; links
that open another site in a new tab need `sandbox_allow_popups`.

The Jinkō interface does not show these keys for a zip archive, but the
embedded application reads them. A person cannot check them in the settings
panel, so always list the ones that you changed.

## Device and data permissions

Each key is a boolean, off by default for every form. Each one gives the page
access to a device or to data of the person who opens the link. **Ask for a yes
for each key before you turn it on:** name the permission, say what the page
gets, and wait. One question for each permission.

| Key | Gives the page |
|---|---|
| `permissions_camera` | The camera. |
| `permissions_microphone` | The microphone. |
| `permissions_geolocation` | The location of the person. |
| `permissions_clipboard_read` | The content of the clipboard. |
| `permissions_clipboard_write` | The right to write to the clipboard. |
| `permissions_display_capture` | A capture of the screen. |
| `permissions_fullscreen` | The full screen. |
| `permissions_web_share` | The share dialog of the device. |

An app that uses a device API (for example `getUserMedia` for the microphone)
shows that it can need the permission. It is not a yes. The browser also asks
the person who opens the link.

## Config of an HTML raw file

| Key | Value | Default | Effect |
|---|---|---|---|
| `config` | A text that holds JSON | `""` | Jinkō gives the parsed value to the page as `window.CONFIG`. |

Give a JSON text, not a dictionary:
`raw_file.update_settings({"config": json.dumps({"dose": 10})})`. Jinkō ignores
a text that is empty or not valid JSON. The page needs
`sandbox_allow_scripts` to read `window.CONFIG`. `config` does not apply to an
embedded application.
