"""
Fetch a Swagger/OpenAPI spec from a URL and print it as JSON.
Usage: python scripts/fetch_swagger.py <url> [--output <file>]

Handles:
- JSON and YAML specs
- Swagger UI HTML pages (extracts the spec URL from the page)
- Basic auth / bearer token via --token flag
"""
import sys
import json
import argparse
import urllib.request
import urllib.error
import re

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
