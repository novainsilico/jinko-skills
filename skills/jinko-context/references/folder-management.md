# Folder Management

Use `../scripts/manage_folders.py` when a user needs to inspect a project's folders or create one. The script loads `.env`, lists every folder, and renders a folders-only tree by default:

```bash
python skills/jinko-context/scripts/manage_folders.py
```

Creating a folder changes the connected project. Confirm the target name and optional parent-folder SID with the user before running either form:

```bash
# Create a root folder.
python skills/jinko-context/scripts/manage_folders.py --create "Analysis"

# Create a direct child of an existing folder SID.
python skills/jinko-context/scripts/manage_folders.py \
  --create "Figures" --parent-id "fo-..."
```

The script refuses to create an exact duplicate below the requested parent.

To rename, recolor, or move a folder, call `folder.update(name=..., color=..., parent=...)` on a `Folder` returned by `client.get_folder(...)`, `client.get_folder_by_name(...)`, or `client.list_folders(...)`. Pass only the fields to change. `parent=None` moves the folder to the project root.

`folder.delete()` deletes the folder, all its descendant folders, and every project item they contain. Show the user the folder tree with its project items and get explicit confirmation before you call it.
