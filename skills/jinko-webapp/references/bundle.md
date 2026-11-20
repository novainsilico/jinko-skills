# Bundle, manifest, and links

## How Jinkō shows a page

- **An HTML raw file is displayed alone.** Jinkō gives the page to the browser
  as text, with no address of its own. A link from the page to a file beside
  it cannot work, and scripts are off by default. Use this form for a page
  that holds everything and needs no script.
- **An embedded application has an address.** Links that are relative to its
  entry page work. Scripts and same-origin are on by default. Use this form
  for a page with scripts or with files beside it.

The script applies this rule: one HTML file with no `<script>` element and no
link to an existing local file goes as `html`; any other web app goes as
`application`. A zip archive with no HTML file and a file of another kind go
as `file`.

## Manifest

The bundle of an embedded application is a zip archive with `manifest.json` at
its top level:

```json
{ "main": "index.html", "version": 1 }
```

- `main` is the path of the entry page in the archive. Required.
- `version` is `1`, the only version. Optional.

The script adds the manifest. It keeps a valid `manifest.json` of the input
as it is. It replaces an invalid one in the bundle and says so in `warnings`:
a web app manifest (PWA) has the same file name, so the app loses it in the
bundle.

The entry page is, in this order: the `main` of a valid manifest, `--entry`,
`index.html` at the top level, the only HTML file. With several HTML files and
no `index.html`, the script stops with `entry_ambiguous`.

## What the script collects

| Input | Files in the bundle |
|---|---|
| One HTML file | The page, and the local files that it links to, at any depth: through HTML attributes, CSS `url()` and `@import`, and relative JavaScript `import`. A file beside the page with no link to it stays out. |
| Directory | Every file, except `.DS_Store`, `Thumbs.db`, `__MACOSX/`, `.git/`, and symbolic links (`files_excluded`). |
| Zip archive | As a directory. One directory that wraps everything is unwrapped. |

## What the script corrects

A link that starts from the root (`/assets/app.js`) cannot work in Jinkō. The
script makes it relative in the bundle (`assets/app.js`, or `../assets/app.js`
from a file in a subdirectory), when its target is a file of the bundle. It
does this in HTML attributes (`src`, `href`, `poster`, `srcset`, `data` of
`object`, inline `style`), in `<style>` blocks, and in CSS files. The report
lists each correction in `links_rewritten`.

## What to relay from the report

- `external_links`: links to other sites, unchanged. They work or not
  according to the settings and to the other site. A script or style from
  another site is a point to tell the person.
- `missing_links`: local links that do not lead to a file of the bundle
  (`not found`, `not a file`, `outside the bundle`). The bundle is valid, but
  that part of the app can fail. Typical causes: a call to a server route
  (`/api/...`), or a file above the given directory.
- `warnings`: read each one to the person in their words.

## Known limits

- **Paths inside JavaScript are not corrected.** A script that names a file
  from the root (`fetch("/data/values.json")`, typical of a build tool with a
  root base path) keeps that path. The script gives a warning for each such
  path that names a file of the bundle. When the app does not find the file
  in Jinkō, the person builds the app again with a relative base path (for
  Vite, `base: "./"`), then pushes again.
- Links that a script builds at run time are not seen: their files can be
  absent from the bundle of a single HTML file. Give the directory instead.
- The script does not build a web app from source code. Give the built
  directory (for example `dist/`).
- A `<base>` element changes how the browser reads relative links; the script
  gives a warning and corrects links as if it was absent.

## Checks and error codes

Before it writes `output_path`, the script checks the bundle as the Jinkō
interface does, and the size limit of 210 MB (210 000 000 bytes). On a failure
it exits with 1, writes no bundle, and gives `error.code` and
`error.message`.

| Code | What to tell the person |
|---|---|
| `input_not_found` | The path does not exist. |
| `no_entry_page` | The directory or archive has no HTML file. |
| `entry_ambiguous` | Ask which page of `error.candidates` starts the app; run again with `--entry`. |
| `entry_missing` | The entry page named by `--entry` or by `manifest.json` is not in the bundle. |
| `manifest_invalid_json`, `manifest_invalid`, `manifest_version_unsupported`, `manifest_schema_unsupported`, `manifest_missing` | The bundle check failed on the manifest; the message says why. |
| `too_large` | The file is above 210 MB. Remove or compress large files. |
| `invalid_archive`, `unsafe_archive` | The zip archive cannot be read, or has unsafe paths. Make it again. |
| `form_not_possible` | The requested form does not fit the input. |
| `output_is_input`, `output_in_input` | Give an `--output` path outside the input. |

## Command

```bash
python skills/jinko-webapp/scripts/bundle_app.py <input> \
  [--output <bundle.zip>] [--entry <page>] \
  [--form auto|html|application] [--report <report.json>]
```

Without `--output`, the bundle goes to a new temporary directory. Report
fields: `ok`, `input`, `input_kind`, `form`, `form_reason`, `entry_page`,
`manifest`, `files`, `files_excluded`, `links_rewritten`, `external_links`,
`missing_links`, `warnings`, `output_path`, `size_bytes`, `size_limit_bytes`,
`error`.
