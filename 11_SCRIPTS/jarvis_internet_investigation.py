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

USER_AGENT = "JarvisLocalInvestigation/1.0 (+local owner research)"
MAX_BYTES = 1_500_000

def slugify(value: str, fallback: str = "investigation") -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.lower()).strip("-")
    return s[:90] or fallback

def fetch_url(url: str, timeout: int = 15) -> dict:
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

def search_duckduckgo(query: str, max_results: int) -> list[dict]:
    url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    fetched = fetch_url(url, timeout=18)
    if not fetched["ok"]:
        return []

    raw = fetched["text"]
    results = []

    pattern = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
    for href, title_html in pattern.findall(raw):
        href = html.unescape(href)
        title = strip_html(title_html)

        parsed = urllib.parse.urlparse(href)
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs:
            href = qs["uddg"][0]

        if href.startswith("//"):
            href = "https:" + href

        if href.startswith("http") and "duckduckgo.com" not in href:
            results.append({"title": title or href, "url": href})

        if len(results) >= max_results:
            break

    return results

def terms_from_query(query: str) -> list[str]:
    raw = re.findall(r"[a-zA-ZÀ-ÿ0-9]{4,}", query.lower())
    stop = {"para", "como", "with", "from", "that", "this", "sobre", "quero", "fazer", "criar"}
    return [x for x in raw if x not in stop][:12]

def extract_findings(text: str, query: str, limit: int = 6) -> list[str]:
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
            if 60 <= len(s) <= 420:
                findings.append(s)
        if len(findings) >= limit:
            break

    if not findings and clean:
        findings.append(clean[:420])

    return findings[:limit]

def investigate(query: str, max_results: int, minutes: int) -> dict:
    created_at = datetime.now().isoformat(timespec="seconds")
    run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slugify(query)}"
    out = OUT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    deadline = time.time() + max(0, minutes) * 60
    started = time.time()

    urls = []
    if re.search(r"https?://", query):
        urls = [{"title": query, "url": u} for u in re.findall(r"https?://\S+", query)]
    else:
        urls = search_duckduckgo(query, max_results=max_results)

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
            "ok": fetched["ok"],
            "status": fetched.get("status"),
            "content_type": fetched.get("content_type", ""),
            "seconds": fetched.get("seconds"),
            "error": fetched.get("error"),
            "findings": findings,
        }
        sources.append(source)

    ok_count = sum(1 for s in sources if s["ok"])
    verdict = "pass" if ok_count else "degraded"

    payload = {
        "created_at": created_at,
        "query": query,
        "verdict": verdict,
        "max_results": max_results,
        "minutes_requested": minutes,
        "seconds_total": round(time.time() - started, 3),
        "source_count": len(sources),
        "ok_source_count": ok_count,
        "sources": sources,
        "limits": {
            "no_paid_api": True,
            "no_login": True,
            "no_private_data": True,
            "search_provider": "DuckDuckGo HTML fallback",
        },
        "next_step": "Use this source pack to generate a plan/spec. Do not call this final truth without reviewing sources.",
    }

    (out / "INVESTIGATION.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# JARVIS Internet Investigation v1",
        "",
        f"Created at: `{created_at}`",
        f"Query: `{query}`",
        f"Verdict: `{verdict}`",
        f"Sources fetched: `{ok_count}/{len(sources)}`",
        "",
        "## Limits",
        "",
        "- No paid API.",
        "- No login/cookies/private pages.",
        "- Search uses public web fallback.",
        "- Findings are extracted snippets, not final truth.",
        "",
        "## Sources",
        "",
    ]

    for s in sources:
        lines.append(f"### {s['index']}. {s['title']}")
        lines.append("")
        lines.append(f"- URL: {s['final_url']}")
        lines.append(f"- OK: `{s['ok']}`")
        lines.append(f"- Status: `{s.get('status')}`")
        if s.get("error"):
            lines.append(f"- Error: `{s['error']}`")
        if s["findings"]:
            lines.append("- Findings:")
            for f in s["findings"]:
                lines.append(f"  - {f}")
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
    parser = argparse.ArgumentParser(description="JARVIS Internet Investigation v1")
    parser.add_argument("query", nargs="*", help="topic, question, or URLs to investigate")
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--minutes", type=int, default=0)
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    if not query:
        query = "JARVIS Agent OS local automation capabilities"

    result = investigate(query=query, max_results=max(1, min(args.max_results, 10)), minutes=max(0, min(args.minutes, 30)))
    payload = result["payload"]

    print("INTERNET_INVESTIGATION_DONE")
    print(result["out"] / "INVESTIGATION.md")
    print(json.dumps({
        "verdict": payload["verdict"],
        "query": payload["query"],
        "source_count": payload["source_count"],
        "ok_source_count": payload["ok_source_count"],
        "seconds_total": payload["seconds_total"],
    }, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
