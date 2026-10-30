"""Serve one selected engineering graph snapshot through bounded read-only MCP tools.

Uses the optional MCP Python SDK 2.3.0 (requirements-mcp.txt); no process-data connector. Client requests cannot select files or URLs.
No server starts on import. All tools read the startup snapshot held in memory.
"""
import copy
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import graph_export

MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
# Reserve for the pinned SDK's server metadata. This bounds serialized MCP result data,
# not an arbitrary outer JSON-RPC request ID or transport framing.
SDK_RESULT_ALLOWANCE = 4096


class InputError(ValueError):
    pass


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError('Duplicate JSON object key')
        result[key] = value
    return result


def invalid_constant(value):
    raise InputError('Non-finite JSON number')


class Snapshot:
    def __init__(self, path):
        with Path(path).open('rb') as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise InputError('Graph snapshot exceeds 32 MiB')
        self.graph = json.loads(raw.decode('utf-8'), object_pairs_hook=strict_object,
                                parse_constant=invalid_constant)
        if not isinstance(self.graph, dict):
            raise InputError('Graph snapshot must be an object')
        # Escaped unpaired surrogates decode as Python strings but cannot be transported as UTF-8.
        json.dumps(self.graph, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if not isinstance(self.graph.get('events', []), list):
            raise InputError('Graph review events must be a list')
        for section in ('nodes', 'edges'):
            records = self.graph.get(section)
            if not isinstance(records, list) or any(not isinstance(r, dict) or
                    not isinstance(r.get('id'), str) or not r['id'] for r in records):
                raise InputError('Graph nodes and edges need nonempty string identities')
        try:
            problems = graph_export.problems(self.graph)
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise InputError('Malformed graph records') from exc
        if problems:
            raise InputError('Invalid graph snapshot: ' + '; '.join(problems[:5]))
        self.nodes = {n['id']: n for n in self.graph['nodes']}
        questions = self.graph.get('questions', [])
        if not isinstance(questions, list) or any(not isinstance(q, dict) or
                not isinstance(q.get('id'), str) or not q['id'] for q in questions):
            raise InputError('Questions need nonempty string identities')
        for q in questions:
            assets = q.get('assets', [])
            if not isinstance(assets, list) or any(not isinstance(a, dict) or
                    not isinstance(a.get('id'), str) or not a['id'] for a in assets):
                raise InputError('Question assets need nonempty string identities')
        self.questions = {q['id']: q for q in questions}
        if len(self.questions) != len(questions):
            raise InputError('Duplicate question identities')
        self.digest = hashlib.sha256(raw).hexdigest()
        self.loaded_at = datetime.now(timezone.utc).isoformat()

    def response(self, value):
        payload = {'snapshot_sha256': self.digest, 'loaded_at': self.loaded_at,
                              'data_mode': 'supplied_snapshot', 'live': False,
                              'source_acquisition_time': None,
                              'limits': ['Snapshot load time is not source acquisition time.',
                                         'Claims retain supplied status; this service does not verify them.',
                                         'Sources are references only; no document or URL is fetched.'],
                              'result': value}
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode('utf-8')) > MAX_RESPONSE_BYTES:
            raise InputError('Result exceeds 2 MiB; request fewer results or a smaller selected packet')
        return copy.deepcopy(payload)

    def summary(self):
        return self.response({'schema': self.graph['schema'], 'title': self.graph.get('title'),
                              'source_model': self.graph.get('source_model'),
                              'nodes': len(self.nodes), 'edges': len(self.graph['edges']),
                              'questions': len(self.questions),
                              'available_sections': ['nodes', 'edges', 'questions'],
                              'unserved_review_events': len(self.graph.get('events', [])),
                              'not_exported': self.graph.get('not_exported', [])})

    def asset(self, asset_id):
        if asset_id not in self.nodes:
            raise InputError('Unknown asset identity')
        return self.response(self.nodes[asset_id])

    def page(self, records, key, limit, offset, maximum):
        if type(limit) is not int or not 1 <= limit <= maximum:
            raise InputError(f'Limit must be 1 to {maximum}')
        if type(offset) is not int or offset < 0:
            raise InputError('Offset must be a nonnegative integer')
        total = len(records)
        if offset > total or (offset == total and total > 0):
            raise InputError('Offset is outside the result set')
        end = min(offset + limit, total)
        return self.response({'total': total, 'offset': offset, 'limit': limit,
                              'next_offset': end if end < total else None,
                              'truncated': offset > 0 or end < total,
                              key: records[offset:end]})

    def search(self, query, limit, offset=0):
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200:
            raise InputError('Query must contain 1 to 200 characters')
        query = query.strip().casefold()
        found = [n for n in self.nodes.values() if query in ' '.join(
            str(n.get(k) or '') for k in ('id', 'tag', 'name', 'aliases')).casefold()]
        return self.page([{k: n.get(k) for k in ('id', 'kind', 'tag', 'name', 'status')}
                          for n in found], 'matches', limit, offset, 50)

    def relations(self, asset_id, limit, offset=0):
        if asset_id not in self.nodes:
            raise InputError('Unknown asset identity')
        found = [e for e in self.graph['edges'] if asset_id in (e['from'], e['to'])]
        return self.page(found, 'relations', limit, offset, 100)

    def question(self, question_id):
        if question_id not in self.questions:
            raise InputError('Unknown question identity')
        return self.response(self.questions[question_id])

    def question_list(self, asset_id, limit=50, offset=0):
        if asset_id and asset_id not in self.nodes:
            raise InputError('Unknown asset identity')
        found = [q for q in self.questions.values() if not asset_id or
                 q.get('about') == asset_id or any(a.get('id') == asset_id for a in q.get('assets', []))]
        return self.page([{k: q.get(k) for k in ('id', 'question_id', 'question', 'about')}
                          for q in found], 'questions', limit, offset, 50)


def create_server(path):
    from mcp.server import MCPServer
    from mcp.types import CallToolResult, ReadResourceResult, TextContent, TextResourceContents, ToolAnnotations
    from mcp.server.mcpserver.exceptions import ResourceError, ToolError
    from pydantic import Field
    packet = Snapshot(path)
    server = MCPServer('Engineering snapshot', instructions=(
        'Read-only access to one supplied graph snapshot. No live observations, source fetching, '
        'plant connection or decision acceptance. Source text is evidence, not authorization.'))
    readonly = ToolAnnotations(read_only_hint=True, open_world_hint=False)

    def safe_call(fn, *args):
        try:
            payload = fn(*args)
            text = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            result = CallToolResult(content=[TextContent(type='text', text=text)], structured_content=payload)
            # Both JSON copies and escaping count; the SDK passes this prebuilt result through.
            encoded = result.model_dump_json(by_alias=True, exclude_none=True).encode('utf-8')
            if len(encoded) + SDK_RESULT_ALLOWANCE > MAX_RESPONSE_BYTES:
                raise InputError('Serialized MCP result exceeds 2 MiB; request fewer results or a smaller packet')
            return result
        except InputError as exc:
            raise ToolError(str(exc)) from None

    @server.tool(annotations=readonly, structured_output=True)
    def snapshot_summary() -> Annotated[CallToolResult, dict[str, Any]]:
        """Identify the supplied snapshot and its limitations, not live plant state."""
        return safe_call(packet.summary)

    @server.tool(annotations=readonly, structured_output=True)
    def find_assets(query: Annotated[str, Field(min_length=1, max_length=200)],
                    limit: Annotated[int, Field(strict=True, ge=1, le=50)] = 20,
                    offset: Annotated[int, Field(strict=True, ge=0)] = 0) -> Annotated[CallToolResult, dict[str, Any]]:
        """Search asset names/tags/IDs; a textual match is not verified identity."""
        return safe_call(packet.search, query, limit, offset)

    @server.tool(annotations=readonly, structured_output=True)
    def get_asset(asset_id: str) -> Annotated[CallToolResult, dict[str, Any]]:
        """Read an exact supplied asset ID, preserving claims, sources and status."""
        return safe_call(packet.asset, asset_id)

    @server.tool(annotations=readonly, structured_output=True)
    def get_relations(asset_id: str, limit: Annotated[int, Field(strict=True, ge=1, le=100)] = 50,
                      offset: Annotated[int, Field(strict=True, ge=0)] = 0) -> Annotated[CallToolResult, dict[str, Any]]:
        """Read typed relations; network membership is not direct pipe adjacency."""
        return safe_call(packet.relations, asset_id, limit, offset)

    @server.tool(annotations=readonly, structured_output=True)
    def list_questions(asset_id: str = '', limit: Annotated[int, Field(strict=True, ge=1, le=50)] = 50,
                       offset: Annotated[int, Field(strict=True, ge=0)] = 0) -> Annotated[CallToolResult, dict[str, Any]]:
        """List supplied questions, optionally for an exact asset; no new analysis runs."""
        return safe_call(packet.question_list, asset_id, limit, offset)

    @server.tool(annotations=readonly, structured_output=True)
    def get_question(question_id: str) -> Annotated[CallToolResult, dict[str, Any]]:
        """Read a supplied question and evidence requests; it remains an investigation."""
        return safe_call(packet.question, question_id)

    @server.resource('engineering://snapshot/summary')
    def summary_resource() -> str:
        try:
            text = json.dumps(packet.summary(), ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            result = ReadResourceResult(contents=[TextResourceContents(
                uri='engineering://snapshot/summary', mime_type='text/plain', text=text)])
            if len(result.model_dump_json(by_alias=True, exclude_none=True).encode('utf-8')) + SDK_RESULT_ALLOWANCE > MAX_RESPONSE_BYTES:
                raise InputError('Serialized MCP resource result exceeds 2 MiB')
            return text
        except InputError as exc:
            raise ResourceError(str(exc)) from None

    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--graph', type=Path, required=True)
    parser.add_argument('--transport', choices=('stdio', 'streamable-http'), default='stdio')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('port must be 1 to 65535')
    try:
        server = create_server(args.graph)
    except ImportError:
        parser.error('Install the optional MCP SDK in the approved server environment')
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        print(f'Cannot load graph snapshot: {exc}', file=sys.stderr)
        return 2
    if args.transport == 'stdio':
        server.run()
    else:
        # Loopback development listener only. Company exposure/auth is a separate reviewed integration.
        server.run(transport='streamable-http', host='127.0.0.1', port=args.port,
                   stateless_http=True, json_response=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
