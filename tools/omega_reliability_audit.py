#!/usr/bin/env python3
"""Omega passive local-website reliability auditor.

Only scans URLs explicitly supplied by the operator. It performs bounded GET/HEAD
requests and does not exploit, brute-force, mutate, crawl, or execute remote code.
Creator attribution: Thomas Lee Harvey.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import socket
import ssl
import sys
import time
from pathlib import Path
from statistics import mean
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SECRET_RE = re.compile(r"(?i)(authorization|cookie|set-cookie|api[_-]?key|token|secret|password)")
ALLOWED_SCHEMES = {"http", "https"}
USER_AGENT = "OmegaReliabilityAudit/1.0 (passive; operator-authorized)"


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key: ("[REDACTED]" if SECRET_RE.search(key) else value[:500]) for key, value in headers.items()}


def validate_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.netloc:
        raise ValueError(f"Only explicit http:// or https:// URLs are allowed: {url}")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are rejected")
    return url.strip()


def tls_observation(url: str, timeout: float) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return {"checked": False, "reason": "not_https"}
    host = parsed.hostname
    port = parsed.port or 443
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=host) as tls:
                cert = tls.getpeercert()
                return {
                    "checked": True,
                    "tls_version": tls.version(),
                    "cipher": tls.cipher()[0] if tls.cipher() else None,
                    "certificate_subject_present": bool(cert.get("subject")),
                    "certificate_expiry_present": bool(cert.get("notAfter")),
                }
    except Exception as exc:
        return {"checked": True, "error_type": type(exc).__name__, "error": str(exc)[:240]}


def probe(url: str, timeout: float = 8.0, max_bytes: int = 256 * 1024) -> dict:
    url = validate_url(url)
    started = time.perf_counter()
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.1"}
    request = Request(url, headers=headers, method="GET")
    result = {"url": url, "checked_at": iso_now(), "method": "GET"}
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(max_bytes + 1)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            text = body[:max_bytes].decode("utf-8", errors="replace")
            response_headers = dict(response.headers.items())
            result.update({
                "status": int(response.status),
                "ok": 200 <= int(response.status) < 400,
                "latency_ms": elapsed_ms,
                "final_url": response.geturl(),
                "content_type": response_headers.get("Content-Type", "")[:200],
                "bytes_sampled": min(len(body), max_bytes),
                "truncated": len(body) > max_bytes,
                "title_present": bool(re.search(r"<title\b[^>]*>.*?</title>", text, re.I | re.S)),
                "headers": redact_headers(response_headers),
            })
    except HTTPError as exc:
        result.update({"status": int(exc.code), "ok": False, "latency_ms": round((time.perf_counter() - started) * 1000, 2), "error_type": "HTTPError", "error": str(exc.reason)[:240], "headers": redact_headers(dict(exc.headers.items()))})
    except (URLError, TimeoutError, socket.timeout) as exc:
        result.update({"status": None, "ok": False, "latency_ms": round((time.perf_counter() - started) * 1000, 2), "error_type": type(exc).__name__, "error": str(exc)[:240]})
    except Exception as exc:
        result.update({"status": None, "ok": False, "latency_ms": round((time.perf_counter() - started) * 1000, 2), "error_type": type(exc).__name__, "error": str(exc)[:240]})
    result["tls"] = tls_observation(url, timeout)
    observed_headers = {key.lower(): value for key, value in result.get("headers", {}).items()}
    result["header_observations"] = {
        "hsts": "strict-transport-security" in observed_headers,
        "content_security_policy": "content-security-policy" in observed_headers,
        "x_content_type_options": "x-content-type-options" in observed_headers,
        "referrer_policy": "referrer-policy" in observed_headers,
        "permissions_policy": "permissions-policy" in observed_headers,
    }
    result["evidence_hash"] = hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()
    return result


def summarize(observations: list[dict]) -> dict:
    successful = [item for item in observations if item.get("ok")]
    latencies = [item["latency_ms"] for item in successful if isinstance(item.get("latency_ms"), (int, float))]
    return {
        "observations": len(observations),
        "successful_observations": len(successful),
        "observed_success_rate_percent": round(len(successful) / len(observations) * 100, 2) if observations else None,
        "mean_latency_ms": round(mean(latencies), 2) if latencies else None,
        "min_latency_ms": min(latencies) if latencies else None,
        "max_latency_ms": max(latencies) if latencies else None,
    }


def render_report(targets: list[str], observations: list[dict], window_hours: float, started_at: str, finished_at: str) -> str:
    groups = {url: [item for item in observations if item["url"] == url] for url in targets}
    lines = [
        "# Omega 48-Hour Reliability Audit",
        "",
        "> **Creator:** Thomas Lee Harvey  ",
        "> **Mode:** Passive, operator-authorized observation only  ",
        f"> **Requested window:** {window_hours:g} hours  ",
        f"> **Observed run:** {started_at} to {finished_at}",
        "",
        "This report does not claim historical uptime from a single run. A 48-hour reliability conclusion requires the monitor to remain active for the requested window and collect repeated observations.",
        "",
        "## Scope and Safety Boundary",
        "",
        "The auditor issued bounded GET requests only to the explicitly supplied URLs. It did not crawl links, submit forms, authenticate, brute-force, exploit, mutate, or execute remote content. Secrets and credential-bearing headers are redacted from evidence.",
        "",
        "## Target Summary",
        "",
        "| Target | Observations | Success rate observed | Mean latency | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for url in targets:
        summary = summarize(groups[url])
        status = "PASS" if summary["observed_success_rate_percent"] == 100 else "REVIEW"
        lines.append(f"| `{url}` | {summary['observations']} | {summary['observed_success_rate_percent']}% | {summary['mean_latency_ms']} ms | {status} |")
    lines += ["", "## Findings", ""]
    for url in targets:
        items = groups[url]
        latest = items[-1] if items else {}
        headers = latest.get("header_observations", {})
        lines.append(f"### `{url}`")
        lines.append("")
        if latest.get("ok"):
            lines.append(f"The latest bounded request returned HTTP **{latest.get('status')}** in **{latest.get('latency_ms')} ms**. Content type was `{latest.get('content_type', '')}` and a title element was {'present' if latest.get('title_present') else 'not observed'}.")
        else:
            lines.append(f"The latest bounded request did not complete successfully: `{latest.get('error_type', 'unknown')}` — {latest.get('error', 'no additional detail')}.")
        missing = [name for name, present in headers.items() if not present]
        lines.append(f"Observed TLS: `{latest.get('tls', {}).get('tls_version', 'not available')}`. Recommended response headers not observed in this response: {', '.join(missing) if missing else 'none'}.")
        lines.append("")
    lines += ["## Recommended 48-Hour Acceptance Criteria", "", "| Criterion | Requirement |", "|---|---|", "| Availability | At least 99.5% successful observations during the full window |", "| Latency | Define a service-specific p95 target before relying on the result |", "| Recovery | Every failure produces a timestamped receipt and bounded recovery attempt |", "| Evidence | Preserve JSON observations and hashes without secrets |", "", "## Limitations", "", "This is a reliability observation tool, not a penetration tester, compliance certification, or guarantee of uptime. DNS, CDN, browser rendering, authenticated flows, background jobs, and dependencies require separate consented checks.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Passive Omega reliability auditor")
    parser.add_argument("urls", nargs="*", help="Explicit http:// or https:// URLs to check")
    parser.add_argument("--url-file", help="File containing one explicit URL per line")
    parser.add_argument("--output-dir", default="omega_audit_output")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--window-hours", type=float, default=48.0)
    parser.add_argument("--repeat", type=int, default=1, help="Number of observations to collect now")
    parser.add_argument("--interval-seconds", type=float, default=300.0)
    args = parser.parse_args(argv)
    targets = list(args.urls)
    if args.url_file:
        targets.extend(line.strip() for line in Path(args.url_file).read_text().splitlines() if line.strip() and not line.lstrip().startswith("#"))
    targets = list(dict.fromkeys(validate_url(url) for url in targets))
    if not targets:
        parser.error("supply at least one explicit URL or --url-file")
    if args.repeat < 1 or args.repeat > 10000:
        parser.error("--repeat must be between 1 and 10000")
    started = iso_now()
    observations = []
    for index in range(args.repeat):
        for url in targets:
            observations.append(probe(url, timeout=args.timeout))
        if index + 1 < args.repeat:
            time.sleep(max(0.0, args.interval_seconds))
    finished = iso_now()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    payload = {"creator": "Thomas Lee Harvey", "requested_window_hours": args.window_hours, "started_at": started, "finished_at": finished, "targets": targets, "observations": observations}
    (output / "observations.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    (output / "omega_48h_reliability_audit.md").write_text(render_report(targets, observations, args.window_hours, started, finished))
    print(f"REPORT_WRITTEN={output / 'omega_48h_reliability_audit.md'}")
    print(f"EVIDENCE_WRITTEN={output / 'observations.json'}")
    print(json.dumps({url: summarize([item for item in observations if item['url'] == url]) for url in targets}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
