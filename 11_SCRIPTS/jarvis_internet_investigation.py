from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO / "05_EXECUCAO" / "203_INTERNET_INVESTIGATION"
OUT_ROOT.mkdir(parents=True, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X) JarvisLocalInvestigation/2.0"
MAX_BYTES = 1_800_000

SEARCH_ENGINES = [
    "duckduckgo_html",
    "duckduckgo_lite",
    "bing",
]

def slugify(value: str, fallback: str = "investigation") -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.lower()).strip("-")
    return s[:90] or fallback

def fetch_url(url: str, timeout: int = 18) -> dict:
    started = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read(MAX_BYTES)
            final_url = res.geturl()
            content_type = res.headers.get("content-type", "")
            status = getattr(res, "status", 200)
        text = raw.decode("utf-8", "replace")
        return {
            "ok": True,
            "status": status,
            "url": url,
            "final_url": final_url,
            "content_type": content_type,
            "text": text,
            "seconds": round(time.time() - started, 3),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "url": url,
            "final_url": url,
            "content_type": "",
            "text": "",
            "error": str(exc),
            "seconds": round(time.time() - started, 3),
        }

def strip_html(value: str) -> str:
    value = re.sub(r"(?is)<script.*?</script>", " ", value)
    value = re.sub(r"(?is)<style.*?</style>", " ", value)
    value = re.sub(r"(?is)<noscript.*?</noscript>", " ", value)
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value

def extract_title(raw_html: str, fallback: str = "") -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw_html or "")
    if not m:
        return fallback or "Untitled"
    return strip_html(m.group(1))[:180] or fallback or "Untitled"

def normalize_result_url(href: str) -> str:
    href = html.unescape(href or "").strip()

    if href.startswith("//"):
        href = "https:" + href

    parsed = urllib.parse.urlparse(href)
    qs = urllib.parse.parse_qs(parsed.query)

    if "uddg" in qs:
        href = qs["uddg"][0]

    if href.startswith("/l/?"):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        if "uddg" in qs:
            href = qs["uddg"][0]

    href = urllib.parse.unquote(href)

    if href.startswith("http"):
        return href

    return ""

def is_good_result_url(url: str) -> bool:
    if not url.startswith("http"):
        return False
    blocked = [
        "duckduckgo.com",
        "bing.com/search",
        "microsoft.com",
        "go.microsoft.com",
        "javascript:",
        "mailto:",
    ]
    return not any(b in url for b in blocked)

def dedupe_results(results: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for item in results:
        url = item.get("url", "")
        if not is_good_result_url(url):
            continue
        key = url.split("#")[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out

def parse_links_from_html(raw: str, engine: str) -> list[dict]:
    results = []

    # Generic anchors. This catches DDG html/lite and Bing variants.
    for href, title_html in re.findall(r'(?is)<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', raw or ""):
        url = normalize_result_url(href)
        title = strip_html(title_html)
        if is_good_result_url(url):
            results.append({
                "title": title or url,
                "url": url,
                "engine": engine,
            })

    # Bing direct b_algo fallback.
    for href, title_html in re.findall(r'(?is)<li[^>]+class=["\']b_algo["\'].*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', raw or ""):
        url = normalize_result_url(href)
        title = strip_html(title_html)
        if is_good_result_url(url):
            results.append({
                "title": title or url,
                "url": url,
                "engine": engine,
            })

    return dedupe_results(results)

def search_duckduckgo_html(query: str) -> list[dict]:
    url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    fetched = fetch_url(url, timeout=18)
    if not fetched["ok"]:
        return []
    return parse_links_from_html(fetched["text"], "duckduckgo_html")

def search_duckduckgo_lite(query: str) -> list[dict]:
    url = "https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({"q": query})
    fetched = fetch_url(url, timeout=18)
    if not fetched["ok"]:
        return []
    return parse_links_from_html(fetched["text"], "duckduckgo_lite")

def search_bing(query: str) -> list[dict]:
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query})
    fetched = fetch_url(url, timeout=18)
    if not fetched["ok"]:
        return []
    return parse_links_from_html(fetched["text"], "bing")

def search_web(query: str, max_results: int) -> tuple[list[dict], list[dict]]:
    attempts = []
    results = []

    for engine, fn in [
        ("duckduckgo_html", search_duckduckgo_html),
        ("duckduckgo_lite", search_duckduckgo_lite),
        ("bing", search_bing),
    ]:
        try:
            found = fn(query)
            attempts.append({"engine": engine, "count": len(found)})
            results.extend(found)
        except Exception as exc:
            attempts.append({"engine": engine, "count": 0, "error": str(exc)})

        results = dedupe_results(results)
        if len(results) >= max_results:
            break

    return results[:max_results], attempts

def direct_urls_from_query(query: str) -> list[dict]:
    urls = re.findall(r"https?://[^\s)>\]\"']+", query)
    clean = []
    for url in urls:
        clean.append({
            "title": url,
            "url": url.rstrip(".,"),
            "engine": "direct_url",
        })
    return dedupe_results(clean)

def manual_search_links(query: str) -> dict:
    q = urllib.parse.urlencode({"q": query})
    return {
        "duckduckgo": "https://duckduckgo.com/?" + q,
        "bing": "https://www.bing.com/search?" + q,
        "google": "https://www.google.com/search?" + q,
    }

def terms_from_query(query: str) -> list[str]:
    raw = re.findall(r"[a-zA-ZÀ-ÿ0-9]{4,}", query.lower())
    stop = {
        "para", "como", "with", "from", "that", "this", "sobre", "quero", "fazer", "criar",
        "professional", "builder", "automation",
    }
    return [x for x in raw if x not in stop][:14]

def extract_findings(text: str, query: str, limit: int = 8) -> list[str]:
    clean = strip_html(text)
    if not clean:
        return []

    terms = terms_from_query(query)
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    findings = []

    for s in sentences:
        low = s.lower()
        if any(t in low for t in terms):
            s = s.strip()
            if 60 <= len(s) <= 480:
                findings.append(s)
        if len(findings) >= limit:
            break

    if not findings and clean:
        findings.append(clean[:480])

    return findings[:limit]

def investigate(query: str, max_results: int, minutes: int) -> dict:
    created_at = datetime.now().isoformat(timespec="seconds")
    run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slugify(query)}"
    out = OUT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    deadline = time.time() + max(0, minutes) * 60
    started = time.time()

    direct = direct_urls_from_query(query)
    search_attempts = []

    if direct:
        urls = direct
    else:
        urls, search_attempts = search_web(query, max_results=max_results)

    sources = []

    for idx, item in enumerate(urls[:max_results], start=1):
        if minutes > 0 and time.time() > deadline:
            break

        fetched = fetch_url(item["url"])
        title = extract_title(fetched.get("text", ""), item.get("title", item["url"]))
        findings = extract_findings(fetched.get("text", ""), query)

        source = {
            "index": idx,
            "title": title,
            "url": item["url"],
            "final_url": fetched.get("final_url", item["url"]),
            "engine": item.get("engine", "unknown"),
            "ok": fetched["ok"],
            "status": fetched.get("status"),
            "content_type": fetched.get("content_type", ""),
            "seconds": fetched.get("seconds"),
            "error": fetched.get("error"),
            "findings": findings,
        }

        sources.append(source)

    ok_count = sum(1 for s in sources if s["ok"] and s.get("findings"))
    fetched_ok = sum(1 for s in sources if s["ok"])

    if ok_count:
        verdict = "pass"
    elif fetched_ok:
        verdict = "partial"
    else:
        verdict = "degraded"

    payload = {
        "created_at": created_at,
        "query": query,
        "verdict": verdict,
        "max_results": max_results,
        "minutes_requested": minutes,
        "seconds_total": round(time.time() - started, 3),
        "source_count": len(sources),
        "ok_source_count": fetched_ok,
        "finding_source_count": ok_count,
        "search_attempts": search_attempts,
        "manual_search_links": manual_search_links(query),
        "sources": sources,
        "limits": {
            "no_paid_api": True,
            "no_login": True,
            "no_private_data": True,
            "search_provider": "DuckDuckGo HTML/Lite + Bing public fallback",
        },
        "next_step": "Use source-backed findings only. If source_count is 0, open manual_search_links or provide URLs directly.",
    }

    (out / "INVESTIGATION.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Internet Investigation v2",
        "",
        f"Created at: `{created_at}`",
        f"Query: `{query}`",
        f"Verdict: `{verdict}`",
        f"Sources fetched: `{fetched_ok}/{len(sources)}`",
        f"Sources with findings: `{ok_count}`",
        "",
        "## Search attempts",
        "",
    ]

    if search_attempts:
        for a in search_attempts:
            lines.append(f"- {a.get('engine')}: `{a.get('count')}` results" + (f" — error: `{a.get('error')}`" if a.get("error") else ""))
    else:
        lines.append("- Direct URL mode or no search attempt needed.")

    lines += [
        "",
        "## Manual search fallback links",
        "",
    ]

    for name, url in payload["manual_search_links"].items():
        lines.append(f"- {name}: {url}")

    lines += [
        "",
        "## Limits",
        "",
        "- No paid API.",
        "- No login/cookies/private pages.",
        "- Findings are extracted snippets, not final truth.",
        "- If this degrades, pass direct URLs to investigate.",
        "",
        "## Sources",
        "",
    ]

    for s in sources:
        lines.append(f"### {s['index']}. {s['title']}")
        lines.append("")
        lines.append(f"- URL: {s['final_url']}")
        lines.append(f"- Engine: `{s.get('engine')}`")
        lines.append(f"- OK: `{s['ok']}`")
        lines.append(f"- Status: `{s.get('status')}`")
        if s.get("error"):
            lines.append(f"- Error: `{s['error']}`")
        if s["findings"]:
            lines.append("- Findings:")
            for f in s["findings"]:
                lines.append(f"  - {f}")
        else:
            lines.append("- Findings: none extracted")
        lines.append("")

    lines += [
        "## Next action",
        "",
        payload["next_step"],
        "",
        "Status real: local internet investigation generated. No production touched.",
    ]

    (out / "INVESTIGATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"out": out, "payload": payload}

def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Internet Investigation v2")
    parser.add_argument("query", nargs="*", help="topic, question, or URLs to investigate")
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--minutes", type=int, default=0)
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    if not query:
        query = "JARVIS Agent OS local automation capabilities"

    result = investigate(
        query=query,
        max_results=max(1, min(args.max_results, 10)),
        minutes=max(0, min(args.minutes, 30)),
    )
    payload = result["payload"]

    print("INTERNET_INVESTIGATION_DONE")
    print(result["out"] / "INVESTIGATION.md")
    print(json.dumps({
        "verdict": payload["verdict"],
        "query": payload["query"],
        "source_count": payload["source_count"],
        "ok_source_count": payload["ok_source_count"],
        "finding_source_count": payload["finding_source_count"],
        "seconds_total": payload["seconds_total"],
    }, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
