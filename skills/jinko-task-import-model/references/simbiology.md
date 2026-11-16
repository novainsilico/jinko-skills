# SimBiology

Jinkō imports a SimBiology model exported as an XLSX workbook. The reference
for the comparison is the user's SimBiology project (`.sbproj`) that the
workbook came from.

## Find MATLAB

Look for a MATLAB MCP server first: search the full tool registry, including
tools that load lazily. Use a local `matlab` command only when no such server
exists. Say which path you use. With no MATLAB at all, give the user the
driver to run and ask for the file it writes.

## Check

1. `prepare-matlab --dir <dir> --project <file.sbproj>` writes
   `check_simbiology.m`. It loads the first model of the project, simulates it
   on the Jinkō time points in seconds with tight tolerances and the project's
   doses, and writes `source.json` with the SimBiology units.
2. Run `check_simbiology.m` in MATLAB with the run directory as the current
   folder: through the MCP server, with `matlab -batch "check_simbiology"`, or
   by the user.
3. Continue with `compare`. It converts the SimBiology units to the Jinkō
   units when the dimensions match.

The driver changes the configset in memory only. Do not save the project. If
some doses are inactive, ask the user whether to activate them for this run.

## Install (optional)

MATLAB and SimBiology need a MathWorks license and a local MATLAB install. The
[MATLAB MCP Server](https://github.com/matlab/matlab-mcp-server) gives the
agent access to it.
