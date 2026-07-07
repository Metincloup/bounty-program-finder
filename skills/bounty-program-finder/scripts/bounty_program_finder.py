#!/usr/bin/env python3
"""Discovery-only bug bounty program finder.

This CLI intentionally does not scan, clone, build, fuzz, exploit, or submit
reports. It turns public/seed bounty program data into ranked discovery records
with explicit source and scope confidence labels.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "1.0.0"
DEFAULT_CACHE_DIR = ".cache/bounty-program-finder"
DEFAULT_TTL_SECONDS = 6 * 60 * 60
USER_AGENT = "bounty-program-finder/1.0"

SEED_URLS = {
    "hackerone": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/hackerone_data.json",
    "bugcrowd": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/bugcrowd_data.json",
    "intigriti": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/intigriti_data.json",
    "yeswehack": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/yeswehack_data.json",
}

GITHUB_RE = re.compile(
    r"(?:https?://|git@)?github\.com[:/](?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)

PROFILE_WEIGHTS = {
    "balanced": {
        "reward": 0.20,
        "github": 0.25,
        "repo_popularity": 0.15,
        "response": 0.15,
        "scope": 0.15,
        "confidence": 0.10,
    },
    "oss_audit": {
        "reward": 0.10,
        "github": 0.35,
        "repo_popularity": 0.20,
        "response": 0.10,
        "scope": 0.15,
        "confidence": 0.10,
    },
    "max_payout": {
        "reward": 0.45,
        "github": 0.15,
        "repo_popularity": 0.10,
        "response": 0.10,
        "scope": 0.10,
        "confidence": 0.10,
    },
    "fast_response": {
        "reward": 0.15,
        "github": 0.15,
        "repo_popularity": 0.10,
        "response": 0.35,
        "scope": 0.15,
        "confidence": 0.10,
    },
    "popular": {
        "reward": 0.15,
        "github": 0.20,
        "repo_popularity": 0.35,
        "response": 0.10,
        "scope": 0.10,
        "confidence": 0.10,
    },
    "low_noise": {
        "reward": 0.15,
        "github": 0.20,
        "repo_popularity": 0.05,
        "response": 0.20,
        "scope": 0.20,
        "confidence": 0.20,
    },
}

LANGUAGE_ALIASES = {
    "python": "python",
    "py": "python",
    "go": "go",
    "golang": "go",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "java": "java",
    "kotlin": "kotlin",
    "swift": "swift",
    "ruby": "ruby",
    "rust": "rust",
    "php": "php",
    "c#": "c#",
    "csharp": "c#",
    "c++": "c++",
    "cpp": "c++",
    "c": "c",
}

PLATFORM_ALIASES = {
    "hackerone": "hackerone",
    "hacker one": "hackerone",
    "h1": "hackerone",
    "bugcrowd": "bugcrowd",
    "intigriti": "intigriti",
    "yeswehack": "yeswehack",
    "yes we hack": "yeswehack",
    "ywh": "yeswehack",
}


JsonDict = Dict[str, Any]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_id(*parts: Any) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "target"


def coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def number_or_unknown(value: Any) -> Any:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    try:
        parsed = float(str(value).replace(",", ""))
    except ValueError:
        return "unknown"
    if parsed.is_integer():
        return int(parsed)
    return parsed


def numeric(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def truthy(value: Any) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes", "y"}


def parse_human_number(value: str) -> Optional[int]:
    match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*([kKmM]?)\s*", value)
    if not match:
        return None
    number = float(match.group(1).replace(",", "."))
    suffix = match.group(2).lower()
    if suffix == "k":
        number *= 1_000
    elif suffix == "m":
        number *= 1_000_000
    return int(number)


def confidence_label(score: float) -> str:
    if score >= 0.85:
        return "verified"
    if score >= 0.70:
        return "high"
    if score >= 0.45:
        return "medium"
    if score > 0:
        return "low"
    return "unknown"


def markdown_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


class FetchError(RuntimeError):
    pass


class Cache:
    def __init__(self, cache_dir: Path, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def get_json(self, key: str, fetcher, refresh: bool = False) -> Tuple[Any, JsonDict]:
        path = self._path(key)
        now = time.time()
        if path.exists() and not refresh:
            age = now - path.stat().st_mtime
            if age <= self.ttl_seconds:
                with path.open("r", encoding="utf-8") as handle:
                    return json.load(handle), {
                        "cache": "hit",
                        "cache_path": str(path),
                        "age_seconds": int(age),
                    }
        data = fetcher()
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
        tmp.replace(path)
        return data, {"cache": "miss", "cache_path": str(path), "age_seconds": 0}


def fetch_json_url(url: str, headers: Optional[JsonDict] = None, timeout: int = 30) -> Any:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    request_headers.update(headers or {})
    req = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        raise FetchError(f"failed to fetch {url}: {exc}") from exc


def fetch_url_status(url: str, timeout: int = 20) -> JsonDict:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}
    req = urllib.request.Request(url, headers=headers, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return {"status_code": response.status, "final_url": response.geturl()}
    except urllib.error.HTTPError as exc:
        if exc.code != 405:
            return {"status_code": exc.code, "final_url": url, "error": str(exc)}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"status_code": "unknown", "final_url": url, "error": str(exc)}

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return {"status_code": response.status, "final_url": response.geturl()}
    except urllib.error.HTTPError as exc:
        return {"status_code": exc.code, "final_url": url, "error": str(exc)}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"status_code": "unknown", "final_url": url, "error": str(exc)}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_target(raw: JsonDict, in_scope: bool) -> JsonDict:
    value = (
        raw.get("asset_identifier")
        or raw.get("target")
        or raw.get("endpoint")
        or raw.get("uri")
        or raw.get("name")
        or ""
    )
    target_type = (raw.get("asset_type") or raw.get("type") or "other").lower()
    description = raw.get("instruction") or raw.get("description") or raw.get("name") or ""
    return {
        "type": target_type,
        "value": normalize_text(value),
        "description": normalize_text(description),
        "in_scope": in_scope,
        "eligible_for_bounty": raw.get("eligible_for_bounty", "unknown"),
        "eligible_for_submission": raw.get("eligible_for_submission", "unknown"),
        "source": "seed",
    }


def normalize_targets(raw_targets: JsonDict) -> JsonDict:
    raw_targets = raw_targets or {}
    in_scope = [normalize_target(item, True) for item in coerce_list(raw_targets.get("in_scope")) if isinstance(item, dict)]
    out_of_scope = [
        normalize_target(item, False) for item in coerce_list(raw_targets.get("out_of_scope")) if isinstance(item, dict)
    ]
    return {
        "authorization_status": "candidate_verification_required",
        "in_scope": in_scope,
        "out_of_scope": out_of_scope,
        "evidence_source": "seed",
        "verification_required": True,
    }


def base_record(platform: str, raw: JsonDict) -> JsonDict:
    name = normalize_text(raw.get("name") or raw.get("handle") or raw.get("id") or "unknown")
    handle = normalize_text(raw.get("handle") or raw.get("id") or slugify(name))
    url = normalize_text(raw.get("url"))
    return {
        "id": stable_id(platform, handle, url, name),
        "program": {
            "name": name,
            "handle": handle or "unknown",
            "platform": platform,
            "url": url or "unknown",
            "website": normalize_text(raw.get("website")) or "unknown",
            "status": normalize_text(raw.get("status") or raw.get("submission_state")) or "unknown",
        },
        "visibility": "unknown",
        "bounty": {
            "offered": "unknown",
            "min": "unknown",
            "max": "unknown",
            "currency": "unknown",
            "source": "seed",
        },
        "metrics": {},
        "scope": normalize_targets(raw.get("targets") or {}),
        "github_repos": [],
        "requirements": {},
        "score": {"value": 0.0, "profile": "balanced", "reasons": [], "missing": []},
        "confidence": {"score": 0.45, "label": "medium", "reasons": ["seed candidate data"]},
        "warnings": ["Seed data is not sufficient authorization; verify official program scope before testing."],
        "sources": [
            {
                "type": "seed",
                "name": "arkadiyt/bounty-targets-data",
                "url": SEED_URLS.get(platform, "unknown"),
            }
        ],
    }


def normalize_hackerone(raw: JsonDict) -> JsonDict:
    record = base_record("hackerone", raw)
    record["visibility"] = "unknown"
    offered = raw.get("offers_bounties")
    record["bounty"].update(
        {
            "offered": bool(offered) if offered is not None else "unknown",
            "currency": "unknown",
        }
    )
    record["metrics"] = {
        "response_efficiency_percentage": number_or_unknown(raw.get("response_efficiency_percentage")),
        "average_time_to_first_program_response": number_or_unknown(raw.get("average_time_to_first_program_response")),
        "average_time_to_bounty_awarded": number_or_unknown(raw.get("average_time_to_bounty_awarded")),
        "average_time_to_report_resolved": number_or_unknown(raw.get("average_time_to_report_resolved")),
    }
    record["requirements"] = {
        "managed_program": raw.get("managed_program", "unknown"),
        "offers_swag": raw.get("offers_swag", "unknown"),
        "allows_bounty_splitting": raw.get("allows_bounty_splitting", "unknown"),
    }
    return record


def normalize_bugcrowd(raw: JsonDict) -> JsonDict:
    record = base_record("bugcrowd", raw)
    record["visibility"] = "public"
    max_payout = number_or_unknown(raw.get("max_payout"))
    record["bounty"].update(
        {
            "offered": isinstance(max_payout, (int, float)) and max_payout > 0,
            "max": max_payout,
            "currency": "USD",
        }
    )
    record["requirements"] = {
        "allows_disclosure": raw.get("allows_disclosure", "unknown"),
        "managed_by_bugcrowd": raw.get("managed_by_bugcrowd", "unknown"),
        "safe_harbor": raw.get("safe_harbor", "unknown"),
    }
    return record


def normalize_intigriti(raw: JsonDict) -> JsonDict:
    record = base_record("intigriti", raw)
    level = normalize_text(raw.get("confidentiality_level")).lower()
    record["visibility"] = "public" if level == "public" else level or "unknown"
    min_bounty = raw.get("min_bounty") or {}
    max_bounty = raw.get("max_bounty") or {}
    record["bounty"].update(
        {
            "offered": isinstance(max_bounty, dict) and bool(max_bounty.get("value")),
            "min": number_or_unknown(min_bounty.get("value") if isinstance(min_bounty, dict) else None),
            "max": number_or_unknown(max_bounty.get("value") if isinstance(max_bounty, dict) else None),
            "currency": (
                max_bounty.get("currency")
                if isinstance(max_bounty, dict) and max_bounty.get("currency")
                else min_bounty.get("currency")
                if isinstance(min_bounty, dict) and min_bounty.get("currency")
                else "unknown"
            ),
        }
    )
    record["requirements"] = {
        "terms_acceptance_required": raw.get("tacRequired", "unknown"),
        "two_factor_required": raw.get("twoFactorRequired", "unknown"),
    }
    return record


def normalize_yeswehack(raw: JsonDict) -> JsonDict:
    record = base_record("yeswehack", raw)
    if raw.get("public") is True:
        record["visibility"] = "public"
    elif raw.get("public") is False:
        record["visibility"] = "private"
    min_bounty = number_or_unknown(raw.get("min_bounty"))
    max_bounty = number_or_unknown(raw.get("max_bounty"))
    record["bounty"].update(
        {
            "offered": isinstance(max_bounty, (int, float)) and max_bounty > 0,
            "min": min_bounty,
            "max": max_bounty,
            "currency": "unknown",
        }
    )
    record["requirements"] = {"disabled": raw.get("disabled", "unknown"), "managed": raw.get("managed", "unknown")}
    return record


NORMALIZERS = {
    "hackerone": normalize_hackerone,
    "bugcrowd": normalize_bugcrowd,
    "intigriti": normalize_intigriti,
    "yeswehack": normalize_yeswehack,
}


class SeedAdapter:
    def __init__(self, cache: Cache, refresh: bool = False):
        self.cache = cache
        self.refresh = refresh

    def load(self) -> Tuple[List[JsonDict], JsonDict]:
        records: List[JsonDict] = []
        summary: JsonDict = {"seed": {}, "errors": []}
        for platform, url in SEED_URLS.items():
            try:
                data, meta = self.cache.get_json(
                    f"seed:{platform}:{url}",
                    lambda url=url: fetch_json_url(url),
                    refresh=self.refresh,
                )
            except FetchError as exc:
                summary["errors"].append({"platform": platform, "error": str(exc)})
                continue
            if not isinstance(data, list):
                summary["errors"].append({"platform": platform, "error": "seed payload is not a list"})
                continue
            normalizer = NORMALIZERS[platform]
            platform_records = [normalizer(item) for item in data if isinstance(item, dict)]
            records.extend(platform_records)
            summary["seed"][platform] = {"count": len(platform_records), **meta, "url": url}
        return records, summary


class GitHubEnricher:
    def __init__(self, cache: Cache, refresh: bool = False):
        self.cache = cache
        self.refresh = refresh
        self.token = os.getenv("GITHUB_TOKEN")

    def enrich(self, records: List[JsonDict], filters: JsonDict, profile: str, limit: int) -> JsonDict:
        summary: JsonDict = {"enabled": True, "token_present": bool(self.token), "repo_metadata_fetches": 0, "searches": 0, "errors": []}
        should_search = bool(filters.get("require_github")) or profile in {"oss_audit", "popular"}
        search_budget = max(limit * 2, 5)
        metadata_budget = max(limit * 5, 20)
        searches_used = 0
        metadata_used = 0

        for record in records:
            candidates = self._extract_explicit_repos(record)
            record["github_repos"] = self._dedupe_repos(candidates)

        for record in records:
            if not record["github_repos"] and should_search and searches_used < search_budget:
                searches_used += 1
                summary["searches"] += 1
                try:
                    inferred = self._search_repo(record)
                    record["github_repos"].extend(inferred)
                except FetchError as exc:
                    summary["errors"].append({"program": record["program"]["name"], "error": str(exc)})

            for repo in record["github_repos"][:3]:
                if metadata_used >= metadata_budget:
                    continue
                try:
                    metadata = self._repo_metadata(repo["full_name"])
                except FetchError as exc:
                    repo["metadata_error"] = str(exc)
                    continue
                metadata_used += 1
                summary["repo_metadata_fetches"] += 1
                repo.update(metadata)

            if record["github_repos"]:
                record["confidence"]["score"] = min(0.85, record["confidence"]["score"] + 0.15)
                record["confidence"]["reasons"].append("GitHub repository candidate found")
                record["confidence"]["label"] = confidence_label(record["confidence"]["score"])
        return summary

    def _github_headers(self) -> JsonDict:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _extract_explicit_repos(self, record: JsonDict) -> List[JsonDict]:
        values: List[Tuple[str, str]] = []
        for target in record["scope"].get("in_scope", []):
            joined = " ".join(
                str(target.get(key, "")) for key in ("value", "description")
            )
            values.append(("explicit_scope", joined))
        for key in ("url", "website"):
            value = record["program"].get(key)
            if value and value != "unknown":
                values.append(("official_link", value))
        repos: List[JsonDict] = []
        for match_type, text in values:
            for match in GITHUB_RE.finditer(text or ""):
                owner = match.group("owner")
                repo_name = match.group("repo").removesuffix(".git")
                full_name = f"{owner}/{repo_name}"
                repos.append(
                    {
                        "full_name": full_name,
                        "url": f"https://github.com/{full_name}",
                        "match_type": match_type,
                        "confidence": "high" if match_type == "explicit_scope" else "medium",
                        "authorization_status": "candidate_verification_required",
                        "source": "seed",
                    }
                )
        return repos

    def _dedupe_repos(self, repos: Sequence[JsonDict]) -> List[JsonDict]:
        seen = set()
        out = []
        for repo in repos:
            key = repo["full_name"].lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(repo)
        return out

    def _search_repo(self, record: JsonDict) -> List[JsonDict]:
        name = record["program"]["name"]
        if not name or name == "unknown":
            return []
        query = f"{name} in:name,description fork:false"
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
            {"q": query, "sort": "stars", "order": "desc", "per_page": 2}
        )
        data, _ = self.cache.get_json(
            f"github-search:{query}",
            lambda: fetch_json_url(url, headers=self._github_headers()),
            refresh=self.refresh,
        )
        repos = []
        for item in data.get("items", []) if isinstance(data, dict) else []:
            full_name = item.get("full_name")
            if not full_name:
                continue
            repos.append(
                {
                    "full_name": full_name,
                    "url": item.get("html_url") or f"https://github.com/{full_name}",
                    "match_type": "inferred",
                    "confidence": "low",
                    "authorization_status": "candidate_verification_required",
                    "source": "github_api",
                    "stars": item.get("stargazers_count", "unknown"),
                    "forks": item.get("forks_count", "unknown"),
                    "language": item.get("language") or "unknown",
                    "pushed_at": item.get("pushed_at") or "unknown",
                }
            )
        return repos

    def _repo_metadata(self, full_name: str) -> JsonDict:
        url = f"https://api.github.com/repos/{full_name}"
        data, _ = self.cache.get_json(
            f"github-repo:{full_name}",
            lambda: fetch_json_url(url, headers=self._github_headers()),
            refresh=self.refresh,
        )
        if not isinstance(data, dict):
            return {}
        license_data = data.get("license") if isinstance(data.get("license"), dict) else {}
        return {
            "stars": data.get("stargazers_count", "unknown"),
            "forks": data.get("forks_count", "unknown"),
            "language": data.get("language") or "unknown",
            "license": license_data.get("spdx_id") or license_data.get("key") or "unknown",
            "topics": data.get("topics", []),
            "pushed_at": data.get("pushed_at") or "unknown",
            "archived": data.get("archived", "unknown"),
        }


class OfficialPageVerifier:
    """Lightweight official program URL reachability check.

    This does not verify scope authorization. It only records whether the
    platform/program URL is reachable as an official public source.
    """

    def __init__(self, cache: Cache, refresh: bool = False):
        self.cache = cache
        self.refresh = refresh

    def enrich(self, records: List[JsonDict]) -> JsonDict:
        summary: JsonDict = {"checked": 0, "reachable": 0, "errors": []}
        for record in records:
            url = record["program"].get("url")
            if not url or url == "unknown" or not str(url).startswith("http"):
                continue
            status, meta = self.cache.get_json(
                f"official-page:{url}",
                lambda url=url: fetch_url_status(url),
                refresh=self.refresh,
            )
            summary["checked"] += 1
            status_code = status.get("status_code") if isinstance(status, dict) else "unknown"
            source = {
                "type": "official_page",
                "name": "program page reachability",
                "url": url,
                "status_code": status_code,
                "cache": meta.get("cache"),
            }
            record.setdefault("sources", []).append(source)
            if isinstance(status_code, int) and 200 <= status_code < 400:
                summary["reachable"] += 1
                record["confidence"]["score"] = min(0.90, record["confidence"]["score"] + 0.05)
                record["confidence"]["label"] = confidence_label(record["confidence"]["score"])
                record["confidence"]["reasons"].append("official program page reachable")
            else:
                summary["errors"].append({"program": record["program"]["name"], "url": url, "status_code": status_code})
        return summary


def credential_summary() -> JsonDict:
    return {
        "github": {"env": "GITHUB_TOKEN", "present": bool(os.getenv("GITHUB_TOKEN"))},
        "hackerone": {
            "env": ["HACKERONE_USERNAME", "HACKERONE_TOKEN"],
            "present": bool(os.getenv("HACKERONE_USERNAME") and os.getenv("HACKERONE_TOKEN")),
        },
        "bugcrowd": {
            "env": ["BUGCROWD_TOKEN_ID", "BUGCROWD_TOKEN_SECRET"],
            "present": bool(os.getenv("BUGCROWD_TOKEN_ID") and os.getenv("BUGCROWD_TOKEN_SECRET")),
        },
        "intigriti": {"env": "INTIGRITI_TOKEN", "present": bool(os.getenv("INTIGRITI_TOKEN"))},
        "yeswehack": {"env": "YESWEHACK_ACCESS_TOKEN", "present": bool(os.getenv("YESWEHACK_ACCESS_TOKEN"))},
        "note": "Credentials are detected only for capability reporting; v1 never writes token values.",
    }


def record_is_private(record: JsonDict) -> bool:
    return str(record.get("visibility", "")).lower() in {"private", "invite-only", "confidential", "application"}


def target_type_matches(record: JsonDict, wanted: Sequence[str]) -> bool:
    if not wanted:
        return True
    wanted_norm = {str(item).lower() for item in wanted}
    for target in record["scope"].get("in_scope", []):
        target_type = str(target.get("type", "")).lower()
        value = str(target.get("value", "")).lower()
        if target_type in wanted_norm:
            return True
        if "source_code" in wanted_norm and "github.com/" in value:
            return True
    return False


def apply_basic_filters(records: Iterable[JsonDict], filters: JsonDict, include_private: bool) -> List[JsonDict]:
    platforms = {str(item).lower() for item in coerce_list(filters.get("platforms") or filters.get("platform"))}
    visibility = {str(item).lower() for item in coerce_list(filters.get("visibility"))}
    scope_types = coerce_list(filters.get("scope_types"))
    min_payout = numeric(filters.get("min_payout"))
    bounty_only = truthy(filters.get("bounty_only"))
    out = []
    for record in records:
        if platforms and record["program"]["platform"] not in platforms:
            continue
        if visibility and str(record.get("visibility", "")).lower() not in visibility:
            continue
        if record_is_private(record) and not include_private:
            continue
        if bounty_only:
            max_payout = numeric(record["bounty"].get("max"))
            offered = record["bounty"].get("offered")
            if offered is not True and not (max_payout is not None and max_payout > 0):
                continue
        if min_payout is not None:
            max_payout = numeric(record["bounty"].get("max"))
            if max_payout is None or max_payout < min_payout:
                continue
        if scope_types and not target_type_matches(record, scope_types):
            continue
        out.append(record)
    return out


def apply_enriched_filters(records: Iterable[JsonDict], filters: JsonDict, require_github: bool, min_confidence: float) -> List[JsonDict]:
    languages = {str(item).lower() for item in coerce_list(filters.get("languages") or filters.get("language"))}
    min_stars = numeric(filters.get("min_stars"))
    min_forks = numeric(filters.get("min_forks"))
    require_github = require_github or truthy(filters.get("require_github"))
    out = []
    for record in records:
        repos = record.get("github_repos", [])
        if require_github and not repos:
            continue
        if languages:
            repo_langs = {str(repo.get("language", "")).lower() for repo in repos}
            if not repo_langs.intersection(languages):
                continue
        if min_stars is not None:
            if not any((numeric(repo.get("stars")) or 0) >= min_stars for repo in repos):
                continue
        if min_forks is not None:
            if not any((numeric(repo.get("forks")) or 0) >= min_forks for repo in repos):
                continue
        if record["confidence"]["score"] < min_confidence:
            continue
        out.append(record)
    return out


def max_payout_score(record: JsonDict) -> float:
    max_payout = numeric(record["bounty"].get("max"))
    if max_payout is None:
        return 0.0
    return min(100.0, math.log10(max(max_payout, 1)) / math.log10(100000) * 100)


def github_score(record: JsonDict) -> float:
    repos = record.get("github_repos") or []
    if not repos:
        return 0.0
    best = 0.0
    for repo in repos:
        match_type = repo.get("match_type")
        if match_type == "explicit_scope":
            best = max(best, 90.0)
        elif match_type == "official_link":
            best = max(best, 65.0)
        elif match_type == "inferred":
            best = max(best, 35.0)
    return best


def repo_popularity_score(record: JsonDict) -> float:
    repos = record.get("github_repos") or []
    if not repos:
        return 0.0
    best = 0.0
    for repo in repos:
        stars = numeric(repo.get("stars")) or 0
        forks = numeric(repo.get("forks")) or 0
        score = min(80.0, math.log10(stars + 1) / math.log10(100000) * 80)
        score += min(20.0, math.log10(forks + 1) / math.log10(10000) * 20)
        best = max(best, score)
    return best


def response_score(record: JsonDict) -> float:
    metrics = record.get("metrics", {})
    response_efficiency = numeric(metrics.get("response_efficiency_percentage"))
    if response_efficiency is not None:
        return min(100.0, max(0.0, response_efficiency))
    first_response = numeric(metrics.get("average_time_to_first_program_response"))
    if first_response is not None:
        return max(0.0, 100.0 - min(first_response, 30.0) / 30.0 * 100.0)
    return 0.0


def scope_score(record: JsonDict) -> float:
    in_count = len(record["scope"].get("in_scope", []))
    out_count = len(record["scope"].get("out_of_scope", []))
    score = min(70.0, in_count * 10.0)
    if out_count:
        score += 10.0
    if any("github.com/" in str(target.get("value", "")).lower() for target in record["scope"].get("in_scope", [])):
        score += 20.0
    return min(100.0, score)


def score_records(records: List[JsonDict], profile: str) -> None:
    weights = PROFILE_WEIGHTS.get(profile, PROFILE_WEIGHTS["balanced"])
    for record in records:
        components = {
            "reward": max_payout_score(record),
            "github": github_score(record),
            "repo_popularity": repo_popularity_score(record),
            "response": response_score(record),
            "scope": scope_score(record),
            "confidence": record["confidence"]["score"] * 100,
        }
        value = sum(components[name] * weight for name, weight in weights.items())
        reasons = []
        if components["github"]:
            reasons.append(f"GitHub match score {components['github']:.0f}")
        if components["reward"]:
            reasons.append(f"Reward signal score {components['reward']:.0f}")
        if components["response"]:
            reasons.append(f"Response signal score {components['response']:.0f}")
        if components["repo_popularity"]:
            reasons.append(f"Repository popularity score {components['repo_popularity']:.0f}")
        missing = [name for name, component in components.items() if component == 0 and name != "confidence"]
        record["score"] = {
            "value": round(value, 2),
            "profile": profile,
            "components": {key: round(val, 2) for key, val in components.items()},
            "reasons": reasons or ["Limited scoring signals available"],
            "missing": missing,
        }


def best_repo(record: JsonDict) -> Optional[JsonDict]:
    repos = record.get("github_repos") or []
    if not repos:
        return None
    return sorted(
        repos,
        key=lambda repo: (
            {"explicit_scope": 3, "official_link": 2, "inferred": 1}.get(repo.get("match_type"), 0),
            numeric(repo.get("stars")) or 0,
        ),
        reverse=True,
    )[0]


def build_handoff(record: JsonDict) -> JsonDict:
    repo = best_repo(record)
    repo_name = repo["full_name"].split("/")[-1] if repo else "unknown"
    scope_evidence = [
        {
            "type": target.get("type"),
            "value": target.get("value"),
            "source": target.get("source", "seed"),
        }
        for target in record["scope"].get("in_scope", [])[:8]
    ]
    exclusions = [
        {
            "type": target.get("type"),
            "value": target.get("value"),
            "source": target.get("source", "seed"),
        }
        for target in record["scope"].get("out_of_scope", [])[:8]
    ]
    return {
        "target_name": record["program"]["name"],
        "repository_url": repo.get("url") if repo else "unknown",
        "repository_path_suggestion": f"./{repo_name}" if repo else "unknown",
        "build_or_run_command_suggestion": "unknown; inspect project documentation before running any build command",
        "main_binary_or_service": "unknown",
        "test_environment": "local lab only; do not contact production or third-party systems",
        "disclosure_platform_or_program": record["program"].get("url", "unknown"),
        "scope_evidence": scope_evidence,
        "exclusions": exclusions,
        "warnings": record.get("warnings", []),
        "authorization_status": record["scope"].get("authorization_status", "candidate_verification_required"),
    }


def add_result_helpers(records: List[JsonDict]) -> None:
    for record in records:
        repo = best_repo(record)
        next_steps = []
        if repo:
            repo_name = repo["full_name"].split("/")[-1]
            next_steps.extend(
                [
                    f"Verify official scope for {repo['url']} before testing.",
                    f"Recommended clone command: git clone {repo['url']}",
                    f"Recommended local path after clone: ./{repo_name}",
                ]
            )
        else:
            next_steps.append("No GitHub repository candidate found; verify official scope manually.")
        record["recommended_next_steps"] = next_steps
        record["master_prompt_handoff"] = build_handoff(record)


def output_document(records: List[JsonDict], filters: JsonDict, profile: str, source_summary: JsonDict, output_format: str) -> str:
    add_result_helpers(records)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "query": filters.get("query") or None,
        "filters": filters,
        "profile": profile,
        "source_summary": source_summary,
        "results": records,
        "master_prompt_handoff": [record["master_prompt_handoff"] for record in records],
    }
    if output_format == "json":
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    markdown = render_markdown(records, filters, profile, source_summary)
    if output_format == "markdown":
        return markdown
    return markdown + "\n```json\n" + json.dumps(payload, indent=2, ensure_ascii=False) + "\n```\n"


def render_markdown(records: List[JsonDict], filters: JsonDict, profile: str, source_summary: JsonDict) -> str:
    lines = []
    lines.append("# Bounty Program Finder Results")
    lines.append("")
    lines.append(f"- Profile: `{profile}`")
    lines.append(f"- Filters: `{json.dumps(filters, ensure_ascii=False, sort_keys=True)}`")
    seed_counts = source_summary.get("seed", {})
    if seed_counts:
        count_text = ", ".join(f"{name}: {meta.get('count', 0)}" for name, meta in sorted(seed_counts.items()))
        lines.append(f"- Seed records loaded: {count_text}")
    if source_summary.get("errors"):
        lines.append(f"- Source warnings: {len(source_summary['errors'])}")
    lines.append("- Safety: verify official scope before testing any target.")
    lines.append("")
    if not records:
        lines.append("No matching programs were found with the current filters.")
        return "\n".join(lines) + "\n"

    lines.append("| Rank | Score | Program | Platform | Bounty | GitHub | Scope Status | Confidence |")
    lines.append("| --- | ---: | --- | --- | --- | --- | --- | --- |")
    for index, record in enumerate(records, 1):
        bounty = record["bounty"]
        bounty_text = reward_text(bounty)
        repo = best_repo(record)
        github_text = repo["full_name"] if repo else "none"
        lines.append(
            "| {rank} | {score:.2f} | [{program}]({url}) | {platform} | {bounty} | {github} | {scope} | {confidence} |".format(
                rank=index,
                score=record["score"]["value"],
                program=markdown_escape(record["program"]["name"]),
                url=record["program"].get("url") if record["program"].get("url") != "unknown" else "",
                platform=record["program"]["platform"],
                bounty=markdown_escape(bounty_text),
                github=markdown_escape(github_text),
                scope=record["scope"]["authorization_status"],
                confidence=record["confidence"]["label"],
            )
        )
    lines.append("")

    for index, record in enumerate(records, 1):
        lines.append(f"## {index}. {record['program']['name']}")
        lines.append("")
        lines.append(f"- Program URL: {record['program'].get('url', 'unknown')}")
        lines.append(f"- Reward: {reward_text(record['bounty'])}")
        lines.append(f"- Visibility: {record.get('visibility', 'unknown')}")
        lines.append(f"- Score reasons: {', '.join(record['score'].get('reasons', []))}")
        metric_text = concise_metrics(record.get("metrics", {}))
        if metric_text:
            lines.append(f"- Metrics: {metric_text}")
        repo = best_repo(record)
        if repo:
            lines.append(f"- GitHub candidate: {repo['url']} (`{repo.get('match_type')}`, {repo.get('confidence')})")
            if repo.get("stars") != "unknown":
                lines.append(f"- Repository metadata: {repo.get('stars')} stars, {repo.get('forks', 'unknown')} forks, {repo.get('language', 'unknown')}")
        else:
            lines.append("- GitHub candidate: none")
        in_scope = record["scope"].get("in_scope", [])[:5]
        out_scope = record["scope"].get("out_of_scope", [])[:5]
        if in_scope:
            lines.append("- In-scope highlights:")
            for target in in_scope:
                lines.append(f"  - `{target.get('type')}` {target.get('value')}")
        if out_scope:
            lines.append("- Out-of-scope / do-not-test highlights:")
            for target in out_scope:
                lines.append(f"  - `{target.get('type')}` {target.get('value')}")
        lines.append("- Warnings:")
        for warning in record.get("warnings", []):
            lines.append(f"  - {warning}")
        lines.append("- Recommended next steps:")
        for step in record.get("recommended_next_steps", []):
            lines.append(f"  - {step}")
        lines.append("")
    return "\n".join(lines)


def reward_text(bounty: JsonDict) -> str:
    offered = bounty.get("offered")
    min_value = bounty.get("min")
    max_value = bounty.get("max")
    currency = bounty.get("currency", "unknown")
    if min_value != "unknown" and max_value != "unknown":
        return f"{min_value}-{max_value} {currency}"
    if max_value != "unknown":
        return f"up to {max_value} {currency}"
    if offered is True:
        return "bounty offered, amount unknown"
    if offered is False:
        return "no bounty indicated"
    return "unknown"


def concise_metrics(metrics: JsonDict) -> str:
    parts = []
    for key in (
        "response_efficiency_percentage",
        "average_time_to_first_program_response",
        "average_time_to_bounty_awarded",
        "average_time_to_report_resolved",
    ):
        value = metrics.get(key)
        if value != "unknown" and value is not None:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def infer_filters_from_query(query: str) -> Tuple[JsonDict, str]:
    text = (query or "").strip()
    lower = text.lower()
    filters: JsonDict = {}
    keywords: List[str] = []

    if not text:
        return filters, "balanced"

    filters["query"] = text

    platforms = []
    for alias, platform in PLATFORM_ALIASES.items():
        if alias in lower and platform not in platforms:
            platforms.append(platform)
    if platforms:
        filters["platforms"] = platforms

    if any(term in lower for term in ("github", "repo", "repository", "açık kaynak", "acik kaynak", "open source", "oss", "source code", "kaynak kod")):
        filters["require_github"] = True
        filters.setdefault("scope_types", [])
        if "source_code" not in filters["scope_types"]:
            filters["scope_types"].append("source_code")
        keywords.extend(["github", "open source"])

    if any(term in lower for term in ("bounty", "ödül", "odul", "ödeme", "odeme", "payout", "reward", "paid", "ücretli", "ucretli")):
        filters["bounty_only"] = True

    if any(term in lower for term in ("private", "invite-only", "invite only", "özel", "ozel", "davet")):
        filters["visibility"] = ["private", "invite-only"]
    elif any(term in lower for term in ("public", "açık program", "acik program", "herkese açık", "herkese acik")):
        filters["visibility"] = ["public"]

    scope_types = set(filters.get("scope_types", []))
    if any(term in lower for term in ("api", "rest", "graphql")):
        scope_types.add("api")
    if any(term in lower for term in ("web", "url", "domain", "subdomain", "wildcard")):
        scope_types.add("url")
    if any(term in lower for term in ("mobile", "android", "ios")):
        scope_types.add("mobile")
    if scope_types:
        filters["scope_types"] = sorted(scope_types)

    languages = []
    for alias, language in LANGUAGE_ALIASES.items():
        if re.search(rf"(?<![a-z0-9+#]){re.escape(alias)}(?![a-z0-9+#])", lower) and language not in languages:
            languages.append(language)
    if languages:
        filters["languages"] = languages

    star_match = re.search(r"(\d+(?:[.,]\d+)?\s*[kKmM]?)\s*(?:\+?\s*)?(?:stars?|star|yıldız|yildiz)", lower)
    if star_match:
        parsed = parse_human_number(star_match.group(1))
        if parsed is not None:
            filters["min_stars"] = parsed

    fork_match = re.search(r"(\d+(?:[.,]\d+)?\s*[kKmM]?)\s*(?:\+?\s*)?(?:forks?|fork)", lower)
    if fork_match:
        parsed = parse_human_number(fork_match.group(1))
        if parsed is not None:
            filters["min_forks"] = parsed

    payout_match = re.search(
        r"(?:min(?:imum)?|at least|en az|minimum)?\s*(?:[$€£]\s*)?(\d+(?:[.,]\d+)?\s*[kKmM]?)(?:\s*(?:usd|eur|gbp|dolar|euro))?",
        lower,
    )
    if payout_match and any(term in lower for term in ("payout", "reward", "bounty", "ödeme", "odeme", "ödül", "odul")):
        parsed = parse_human_number(payout_match.group(1))
        if parsed is not None and parsed >= 50:
            filters["min_payout"] = parsed

    if "usd" in lower or "$" in lower or "dolar" in lower:
        filters["currency"] = "USD"
    elif "eur" in lower or "€" in lower or "euro" in lower:
        filters["currency"] = "EUR"
    elif "gbp" in lower or "£" in lower:
        filters["currency"] = "GBP"

    if any(term in lower for term in ("popular", "popüler", "populer", "rağbet", "ragbet", "star", "yıldız", "yildiz")):
        keywords.append("popular")
    if any(term in lower for term in ("fast response", "hızlı dönüş", "hizli donus", "triage", "response time", "çabuk", "cabuk")):
        keywords.append("fast response")
    if any(term in lower for term in ("max payout", "highest payout", "en yüksek ödeme", "en yuksek odeme", "çok ödeyen", "cok odeyen")):
        keywords.append("max payout")
    if any(term in lower for term in ("low noise", "az rekabet", "az rağbet", "az ragbet", "less competition")):
        keywords.append("low noise")

    if keywords:
        filters["keywords"] = sorted(set(keywords))

    return filters, infer_profile_from_query(lower, filters)


def infer_profile_from_query(lower_query: str, filters: JsonDict) -> str:
    if any(term in lower_query for term in ("max payout", "highest payout", "en yüksek ödeme", "en yuksek odeme", "çok ödeyen", "cok odeyen")):
        return "max_payout"
    if any(term in lower_query for term in ("fast response", "hızlı dönüş", "hizli donus", "triage", "response time", "çabuk", "cabuk")):
        return "fast_response"
    if any(term in lower_query for term in ("low noise", "az rekabet", "az rağbet", "az ragbet", "less competition")):
        return "low_noise"
    if filters.get("require_github"):
        return "oss_audit"
    if any(term in lower_query for term in ("popular", "popüler", "populer", "rağbet", "ragbet", "star", "yıldız", "yildiz")):
        return "popular"
    return "balanced"


def parse_filters(value: str) -> JsonDict:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--filters-json must be valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("--filters-json must decode to an object")
    return data


def merge_filters(query_filters: JsonDict, explicit_filters: JsonDict) -> JsonDict:
    merged = dict(query_filters)
    for key, value in explicit_filters.items():
        if isinstance(value, list) and isinstance(merged.get(key), list):
            existing = list(merged[key])
            for item in value:
                if item not in existing:
                    existing.append(item)
            merged[key] = existing
        else:
            merged[key] = value
    return merged


def run(args: argparse.Namespace) -> str:
    explicit_filters = parse_filters(args.filters_json)
    query_filters, inferred_profile = infer_filters_from_query(args.query or "")
    filters = merge_filters(query_filters, explicit_filters)
    profile = inferred_profile if args.profile == "auto" else args.profile
    if profile not in PROFILE_WEIGHTS:
        profile = "balanced"
    cache = Cache(Path(args.cache_dir), ttl_seconds=args.cache_ttl_seconds)
    records, source_summary = SeedAdapter(cache, refresh=args.refresh).load()
    source_summary["query_inference"] = {
        "query": args.query or None,
        "inferred_profile": inferred_profile,
        "explicit_profile": args.profile,
        "effective_profile": profile,
        "inferred_filters": query_filters,
    }
    source_summary["credentials"] = credential_summary()
    records = apply_basic_filters(records, filters, include_private=args.include_private)

    github_summary = GitHubEnricher(cache, refresh=args.refresh).enrich(records, filters, profile, args.limit)
    source_summary["github"] = github_summary

    score_records(records, profile)
    min_confidence = args.min_confidence
    if filters.get("min_confidence") is not None:
        parsed = numeric(filters.get("min_confidence"))
        if parsed is not None:
            min_confidence = parsed
    records = apply_enriched_filters(records, filters, require_github=args.require_github, min_confidence=min_confidence)
    records.sort(key=lambda record: record["score"]["value"], reverse=True)
    records = records[: args.limit]
    source_summary["official_pages"] = OfficialPageVerifier(cache, refresh=args.refresh).enrich(records)
    score_records(records, profile)
    records.sort(key=lambda record: record["score"]["value"], reverse=True)
    return output_document(records, filters, profile, source_summary, args.format)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Find and rank bug bounty programs for safe audit handoff.")
    parser.add_argument("--query", default="", help="Natural-language discovery request; merged with --filters-json.")
    parser.add_argument("--filters-json", default="{}", help="JSON object using references/filter-schema.md.")
    parser.add_argument("--profile", default="auto", choices=["auto", *sorted(PROFILE_WEIGHTS)], help="Ranking profile.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum rich records to return.")
    parser.add_argument("--format", choices=["markdown", "json", "both"], default="both", help="Output format.")
    parser.add_argument("--refresh", action="store_true", help="Bypass cache and fetch fresh data.")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR, help="Workspace cache directory.")
    parser.add_argument("--cache-ttl-seconds", type=int, default=DEFAULT_TTL_SECONDS, help="Cache TTL.")
    parser.add_argument("--include-private", action="store_true", help="Include private/invite-only programs if accessible in data.")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Minimum confidence score from 0.0 to 1.0.")
    parser.add_argument("--require-github", action="store_true", help="Require at least one GitHub repository candidate.")
    parser.add_argument("--output", help="Write output to a file instead of stdout.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    document = run(args)
    if args.output:
        Path(args.output).write_text(document, encoding="utf-8")
    else:
        sys.stdout.write(document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
