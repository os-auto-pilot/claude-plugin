"""
Fetch a Swagger/OpenAPI spec from a URL and print it as JSON.
Usage: python skills/analyze-requirements/scripts/fetch_swagger.py <url> [--output <file>]

Handles:
- JSON and YAML specs
- Swagger UI HTML pages (extracts the spec URL from the page)
- Basic auth / bearer token via --token flag

When --output is given, also writes a companion "<output>.endpoints.json"
file: one flattened entry per operation (method + path) with its request
content-type(s), request fields (with file-upload fields flagged), path/
query/header parameters, auth requirements, and response status codes.
This exists so nothing has to be re-derived by eyeballing a large raw spec —
in particular, multipart/form-data endpoints and their file fields are
called out explicitly instead of being easy to miss.
"""
import sys
import json
import argparse
import urllib.request
import urllib.error
import re
import os

def fetch_url(url, token=None):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json, application/yaml, text/yaml, */*")
    req.add_header("User-Agent", "oniesoft-swagger-fetcher/1.0")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8"), resp.headers.get("Content-Type", "")

def try_parse_json(text):
    try:
        return json.loads(text)
    except Exception:
        return None

def try_parse_yaml(text):
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        return None
    except Exception:
        return None

def extract_spec_url_from_html(html, base_url):
    """Try to find the swagger spec URL embedded in a Swagger UI page."""
    patterns = [
        r'url\s*:\s*["\']([^"\']+\.(?:json|yaml|yml)[^"\']*)["\']',
        r'"url"\s*:\s*"([^"]+\.(?:json|yaml|yml)[^"]*)"',
        r'SwaggerUIBundle\([^)]*url\s*:\s*["\']([^"\']+)["\']',
        r'href=["\']([^"\']*(?:swagger|openapi|api-docs)[^"\']*\.(?:json|yaml|yml))["\']',
        r'src=["\']([^"\']*(?:swagger|openapi|api-docs)[^"\']*\.(?:json|yaml|yml))["\']',
        # FastAPI / Flask-RESTX / Django REST style
        r'"openapi":\s*"[^"]*"',  # inline JSON in script tag
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m and not pat.startswith('"openapi"'):
            found = m.group(1)
            if found.startswith("http"):
                return found
            # relative URL — resolve against base
            from urllib.parse import urljoin
            return urljoin(base_url, found)

    # Check for inline spec in <script> tag
    script_match = re.search(r'<script[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    if script_match:
        script_content = script_match.group(1)
        if '"openapi"' in script_content or '"swagger"' in script_content:
            inline = try_parse_json(script_content.strip())
            if inline:
                return None  # signal: inline spec found, return it directly

    # Common default paths to try
    from urllib.parse import urljoin, urlparse
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    common_paths = [
        "/openapi.json", "/swagger.json", "/api-docs", "/api/swagger.json",
        "/v1/openapi.json", "/v2/api-docs", "/v3/api-docs",
        "/swagger/v1/swagger.json", "/api/openapi.json",
    ]
    return [urljoin(base, p) for p in common_paths]

def fetch_spec(url, token=None):
    text, content_type = fetch_url(url, token)

    # Direct JSON spec
    if "json" in content_type or text.strip().startswith("{") or text.strip().startswith("["):
        spec = try_parse_json(text)
        if spec and ("openapi" in spec or "swagger" in spec or "paths" in spec):
            return spec, url

    # Direct YAML spec
    if "yaml" in content_type or "yml" in url:
        spec = try_parse_yaml(text)
        if spec and isinstance(spec, dict) and ("openapi" in spec or "swagger" in spec or "paths" in spec):
            return spec, url

    # HTML page — look for embedded spec URL
    if "html" in content_type or text.strip().lower().startswith("<!doc") or "<html" in text[:500].lower():
        result = extract_spec_url_from_html(text, url)
        if isinstance(result, list):
            # Try common paths
            for candidate_url in result:
                try:
                    spec, final_url = fetch_spec(candidate_url, token)
                    if spec:
                        return spec, final_url
                except Exception:
                    continue
        elif result:
            return fetch_spec(result, token)
        # Last resort: try parsing JSON from script tags
        matches = re.findall(r'(\{[^{}]{50,}\})', text)
        for m in matches:
            spec = try_parse_json(m)
            if spec and ("openapi" in spec or "swagger" in spec):
                return spec, url

    # Try YAML parse as fallback
    spec = try_parse_yaml(text)
    if spec and isinstance(spec, dict) and ("openapi" in spec or "swagger" in spec or "paths" in spec):
        return spec, url

    raise ValueError(f"Could not extract OpenAPI/Swagger spec from {url}.\nContent-Type: {content_type}\nFirst 500 chars:\n{text[:500]}")


# ---------------------------------------------------------------------------
# Per-endpoint metadata extraction (content-type, fields, params, auth, responses)
# ---------------------------------------------------------------------------

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head")
_CONSTRAINT_KEYS = ("format", "minLength", "maxLength", "minimum", "maximum", "pattern", "enum", "example", "description")

def _resolve_ref(spec, ref):
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return {}
    node = spec
    for part in ref.lstrip("#/").split("/"):
        if not isinstance(node, dict):
            return {}
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}

def _resolve(spec, node):
    if isinstance(node, dict) and "$ref" in node:
        return _resolve(spec, _resolve_ref(spec, node["$ref"]))
    return node if isinstance(node, dict) else {}

def _extract_schema_fields(spec, schema):
    """Flatten schema.properties into field dicts; flags OpenAPI3 file uploads (type=string, format=binary)."""
    schema = _resolve(spec, schema)
    props = schema.get("properties", {}) or {}
    required = set(schema.get("required", []) or [])
    fields = []
    for name, prop in props.items():
        prop = _resolve(spec, prop)
        field = {"name": name, "type": prop.get("type"), "required": name in required}
        for key in _CONSTRAINT_KEYS:
            if key in prop:
                field[key] = prop[key]
        if prop.get("type") == "string" and prop.get("format") == "binary":
            field["is_file"] = True
        fields.append(field)
    return fields

def _extract_content_types_and_fields(spec, operation):
    """Returns (content_types, fields) — merges OpenAPI 3.x requestBody and Swagger 2.0 body/formData shapes."""
    content_types = []
    fields = []

    # OpenAPI 3.x
    request_body = _resolve(spec, operation.get("requestBody", {}))
    for ct, media in (request_body.get("content") or {}).items():
        content_types.append(ct)
        fields.extend(_extract_schema_fields(spec, media.get("schema", {})))

    # Swagger 2.0
    for ct in operation.get("consumes") or []:
        if ct not in content_types:
            content_types.append(ct)
    for param in operation.get("parameters") or []:
        param = _resolve(spec, param) or param
        if not isinstance(param, dict):
            continue
        location = param.get("in")
        if location == "body":
            fields.extend(_extract_schema_fields(spec, param.get("schema", {})))
        elif location == "formData":
            field = {"name": param.get("name"), "type": param.get("type"), "required": bool(param.get("required"))}
            for key in _CONSTRAINT_KEYS:
                if key in param:
                    field[key] = param[key]
            if param.get("type") == "file":
                field["is_file"] = True
            fields.append(field)

    return content_types, fields

def _extract_parameters(operation, location):
    """path / query / header parameters (excludes body / formData)."""
    result = []
    for param in operation.get("parameters") or []:
        if not isinstance(param, dict) or param.get("in") != location:
            continue
        entry = {"name": param.get("name"), "required": bool(param.get("required"))}
        param_schema = param.get("schema")
        schema = param_schema if isinstance(param_schema, dict) else param
        for key in ("type", "format", "minimum", "maximum", "minLength", "maxLength", "pattern", "enum"):
            if key in schema:
                entry[key] = schema[key]
        result.append(entry)
    return result

def _extract_responses(spec, operation):
    responses = {}
    for status, resp in (operation.get("responses") or {}).items():
        resp = _resolve(spec, resp)
        entry = {"description": resp.get("description", "")}
        schema = None
        for media in (resp.get("content") or {}).values():
            schema = media.get("schema")
            break
        if schema is None and "schema" in resp:
            schema = resp["schema"]
        if schema:
            props = _resolve(spec, schema).get("properties")
            if props:
                entry["fields"] = list(props.keys())
        responses[str(status)] = entry
    return responses

def _security_names(spec, operation):
    security = operation.get("security", spec.get("security", []))
    names = []
    for requirement in security or []:
        names.extend(requirement.keys())
    return names

def build_endpoint_summary(spec):
    """One flattened entry per (method, path) operation — see module docstring for shape."""
    endpoints = []
    for path, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        shared_params = path_item.get("parameters", []) or []
        for method in _HTTP_METHODS:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            merged = dict(operation)
            merged["parameters"] = shared_params + (operation.get("parameters") or [])

            content_types, request_fields = _extract_content_types_and_fields(spec, merged)
            if not content_types and request_fields:
                content_types = ["application/json"]

            entry = {
                "method": method.upper(),
                "path": path,
                "operationId": operation.get("operationId"),
                "summary": operation.get("summary") or operation.get("description"),
                "content_types": content_types,
                "auth": _security_names(spec, operation),
                "path_parameters": _extract_parameters(merged, "path"),
                "query_parameters": _extract_parameters(merged, "query"),
                "header_parameters": _extract_parameters(merged, "header"),
                "request_fields": request_fields,
                "responses": _extract_responses(spec, operation),
            }

            is_multipart = any("multipart/form-data" in ct for ct in content_types)
            has_file_field = any(f.get("is_file") for f in request_fields)
            if is_multipart or has_file_field:
                entry["note"] = (
                    "multipart/form-data endpoint — use the 'with form data' step for non-file fields "
                    "and the 'with file params' step for file fields (see SKILL.md), NOT 'with body'."
                )

            endpoints.append(entry)
    return endpoints


def main():
    parser = argparse.ArgumentParser(description="Fetch a Swagger/OpenAPI spec from a URL")
    parser.add_argument("url", help="Swagger UI or spec URL")
    parser.add_argument("--output", "-o", help="Write spec JSON to this file instead of stdout")
    parser.add_argument("--token", help="Bearer token for auth")
    args = parser.parse_args()

    try:
        spec, resolved_url = fetch_spec(args.url, args.token)
        output = json.dumps(spec, indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Spec saved to {args.output} (resolved from {resolved_url})", file=sys.stderr)

            endpoints = build_endpoint_summary(spec)
            summary_path = os.path.splitext(args.output)[0] + ".endpoints.json"
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(endpoints, f, indent=2, ensure_ascii=False)
            multipart_count = sum(1 for e in endpoints if "note" in e)
            print(
                f"Endpoint summary saved to {summary_path} "
                f"({len(endpoints)} endpoints, {multipart_count} flagged as multipart/form-data)",
                file=sys.stderr,
            )
        else:
            print(output)
    except urllib.error.URLError as e:
        print(f"ERROR: Could not connect to {args.url}: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
