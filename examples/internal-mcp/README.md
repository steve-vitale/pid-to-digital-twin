# Read an approved engineering snapshot through MCP

This starter lets an approved local MCP client search one supplied graph and read assets, typed relationships
and investigation questions. The source claims and their statuses remain attached. It is an access layer for a
first evidence packet; the company's existing systems retain ongoing ownership, permissions and decisions.

The default reader still uses [approved Copilot with selected documents](../../docs/INTERNAL_CONNECTIVITY.md).
The steps below are for an IT developer with installation rights in an approved environment. They are tested
with public example data and an SDK client, not a company Copilot tenant or an operations network. The server
does not fetch source documents, collect process data, accept decisions or execute changes.

## Try the public example

Use Python 3.10+ and a separate environment approved for the optional SDK. Package installation may contact a
package repository; use the company's approved mirror where required. Installing the SDK does not configure
any assistant client, company account or firewall.

```sh
python -m pip install -r requirements-mcp.txt
python scripts/check_snapshot_mcp.py
```

The check builds a graph from the committed `data/bayer_rt/process_model.json` and
`examples/opportunity-screen/bayer/questions.json`, serialized as UTF-8 JSON with LF endings, one-space indent
and a final newline. It uses temporary local files and tests in-memory, stdio and loopback HTTP clients. It
starts one temporary listener on `127.0.0.1`, then stops it. It needs no account, API key, model call, source
download or plant connection. A successful check is local protocol evidence only.

For a client that supports local stdio servers, configure its executable and arguments as:

```sh
python scripts/serve_snapshot.py --graph examples/graph-export/bayer_graph.json
```

The client starts this process and communicates over stdin/stdout; it does not need a listening network port.
Commands here assume the repository root. In the client's own configuration, use absolute paths to the approved
Python executable, server script and selected snapshot; configuration syntax depends on the client.
Do not run it in a terminal expecting an interactive chat. The selected file is read once at startup and stays
in memory. Replacing the file does not refresh a running server. Restart with a newly cleared packet to load a
new version, and check its returned SHA-256 before continuing an investigation.

For a local developer's Streamable HTTP test:

```sh
python scripts/serve_snapshot.py --graph examples/graph-export/bayer_graph.json --transport streamable-http --port 8000
```

The endpoint is `http://127.0.0.1:8000/mcp`. The listener is fixed to loopback, with no host override. This mode
has no company authentication and is not a shared deployment. The host and client must already be approved to
handle the selected content; a local listener does not isolate it from other users or processes on that host.

## What each piece contributes

| Tool or resource | Contribution | Boundary |
|---|---|---|
| `snapshot_summary` | Identifies the loaded file by SHA-256, load time and section counts. | Load time is not the acquisition time or effective date of a source. Review events are counted but not served. |
| `find_assets(query, limit, offset)` | Finds supplied IDs, names, tags and aliases. | Text matches do not verify physical identity. Search results are summaries; use `get_asset` for claims and sources. |
| `get_asset(asset_id)` | Returns the complete supplied asset record, including sourced claims and review status. | The server preserves those claims; it does not independently verify them. |
| `get_relations(asset_id, limit, offset)` | Returns the supplied typed, directed relationships. | Network co-membership must not be read as direct pipe adjacency. |
| `list_questions(asset_id, limit, offset)` | Finds the existing investigation questions, optionally for one asset. | It does not run the question engine or resolve a question. |
| `get_question(question_id)` | Returns a full supplied question, its evidence and data requests. | A question or recommendation is not an accepted change or operating instruction. |
| `engineering://snapshot/summary` | Offers the same summary as an MCP resource. | Client support for resources varies; the summary tool is available separately. |

The server reads existing [twin-graph-1](../../docs/GRAPH_EXPORT.md) JSON. The standalone commands above use
`examples/graph-export/bayer_graph.json`, which has no attached questions and has a different fingerprint from
the checker snapshot. To include questions, export them with the graph rather than assuming every graph
already contains them:

```sh
python scripts/graph_export.py data/bayer_rt/process_model.json --questions examples/opportunity-screen/bayer/questions.json --out my_graph.json
python scripts/serve_snapshot.py --graph my_graph.json
```

Source references are returned as data and are never opened. Tool callers cannot supply a file path or fetch
URL. A supplied asset whose identity looks like a path is still just an opaque ID. No write tool is exposed.
Source text is evidence to inspect, not authorization for the client to run instructions found inside it.

Search and question pages allow 1–50 results; relationships allow 1–100. Start at `offset=0` and follow
`next_offset` until it is `null`. Ordering is stable within the loaded snapshot. Keep pages only when their
`snapshot_sha256` values agree. Invalid offsets and unknown IDs return errors; an empty first page is valid.
`truncated` means the page does not contain the entire matching set, including when it is a later page.

Input is capped at 32 MiB. Application responses and serialized successful MCP result data are bounded at
2 MiB, including duplicated text/structured JSON and escaping, with a 4 KiB allowance for pinned SDK metadata.
This is not a bound on arbitrary outer JSON-RPC request IDs or transport framing. A large single record is
refused rather than silently losing claims. Request fewer items or prepare a smaller cleared packet; this is
a starter for bounded investigations, not an enterprise search service.

## Company and operations boundaries

Select a packet that every authorized user of that process may read. The starter has no per-user source
authorization, SSO, tenant administration, audit service or permission-revocation integration. Those are
required design and validation work before a company shared service can use a broadly scoped collection.

Copilot Studio's documented MCP route uses Streamable transport and requires approved reachability, policy and
authentication. A local stdio process or loopback URL is not a reachable cloud endpoint. No published Copilot
channel has been tested here. See the [company connectivity guide](../../docs/INTERNAL_CONNECTIVITY.md) before
planning that integration; do not expose this anonymous starter through a public tunnel.

If the plant permits no cross-boundary ports, the workflow stays disconnected. Use only snapshots released
through a transfer method the site already allows, if any; no allowed transfer means no process-data access.
An OT-local server does not give cloud Copilot a route into OT. Existing one-way replication and an explicitly
approved cross-zone service are separate site architectures, not settings enabled by this script.

## Evidence and limits

The [sample asset response](sample_asset.json) is a recorded `Snapshot.asset` application response for `P-1`
from the generated Bayer snapshot with questions, using the two inputs and canonical serialization above. The
protocol checker separately exercises this response through the SDK. Its SHA-256
identifies that generated file, not the plain committed graph used in the standalone commands. Its load
timestamp records this local snapshot load and its source acquisition time is unknown. The checker compares
the full asset to the committed input, checks typed relationships/questions, traverses larger synthetic pages,
and exercises expected errors without losing the session. Regression controls also cover malformed inputs,
size/escaping limits, snapshot immutability and refusal without source fetching.

The optional CI job installs the pinned [official MCP Python SDK release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0)
and runs those protocol checks separately from the base toolkit suite. Local development has exercised both
negotiated `2025-11-25` and `2026-07-28` protocol modes; this does not establish compatibility with every client.
Company authentication, Copilot channels, historian connections, native imports and operational value remain
unvalidated. This feature adds snapshot access, not additional corpus cells or description-to-P&ID accuracy.
