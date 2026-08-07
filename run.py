#!/usr/bin/env python3
"""Entrypoint: fetch arxiv -> dedupe -> filter by author institutional
affiliation -> render feed -> publish.
"""
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from lib import affiliation, arxiv_fetch, publish, render, store

REPO_DIR = Path(__file__).resolve().parent


def load_config():
    with open(REPO_DIR / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(log_path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stdout)],
    )


def write_last_run(path, summary):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def main():
    config = load_config()
    paths = config["paths"]
    setup_logging(REPO_DIR / paths["log_file"])
    log = logging.getLogger("arxiv-feed")
    run_started_at = datetime.now(timezone.utc)
    log.info("=== run start ===")

    aff_config = config["affiliation"]
    institutions = affiliation.load_institutions(REPO_DIR / aff_config["institutions_file"])
    scratch_dir = REPO_DIR / paths["pdf_scratch_dir"]
    pdf_timeout = aff_config["pdf_fetch_timeout_seconds"]
    pdf_delay = aff_config["pdf_fetch_delay_seconds"]

    seen_ids = store.load_json(REPO_DIR / paths["seen_ids"], {})
    published_items = store.load_json(REPO_DIR / paths["published_items"], [])

    papers, failed_categories = arxiv_fetch.fetch_all(config["categories"])
    for category, error in failed_categories:
        log.warning("category %s failed to fetch, skipping this run: %s", category, error)

    new_papers = [p for p in papers if not store.is_seen(seen_ids, p["arxiv_id"])]
    log.info(
        "fetched %d papers (%d already seen, %d new)",
        len(papers), len(papers) - len(new_papers), len(new_papers),
    )

    window_size = config["feed"]["window_size"]

    included_count = 0
    pdf_errors = 0

    for paper in new_papers:
        result = affiliation.check_affiliation(paper, institutions, scratch_dir, timeout=pdf_timeout)
        time.sleep(pdf_delay)

        if result["error"]:
            pdf_errors += 1
            log.warning("pdf fetch/parse failed for %s, leaving unseen for retry next run: %s", paper["arxiv_id"], result["error"])
            continue  # not recorded as seen - retried next run

        judged_at = datetime.now(timezone.utc).isoformat()
        store.record_seen(seen_ids, paper["arxiv_id"], result["included"], judged_at)

        if result["included"]:
            included_count += 1
            reason = ", ".join(result["matched_institutions"])
            item = {**paper, "judged_at": judged_at, "reason": reason}
            published_items = store.add_relevant_item(published_items, item, window_size)
            log.info("INCLUDED %s (%s) - %s", paper["arxiv_id"], paper["title"][:70], reason)

    log.info("%d of %d new papers included (%d pdf errors)", included_count, len(new_papers), pdf_errors)

    store.save_json(REPO_DIR / paths["seen_ids"], seen_ids)
    store.save_json(REPO_DIR / paths["published_items"], published_items)

    feed_config = config["feed"]
    render.write_feed(
        published_items,
        feed_config["title"],
        feed_config["link"],
        feed_config["description"],
        REPO_DIR / paths["feed_output"],
    )
    log.info("wrote feed with %d items to %s", len(published_items), paths["feed_output"])

    success, message = publish.commit_and_push(
        str(REPO_DIR), paths["feed_output"], f"update feed: {included_count} new relevant papers"
    )
    log.log(logging.INFO if success else logging.ERROR, "publish: %s", message)

    log.info("=== run end ===")

    write_last_run(REPO_DIR / "state" / "last_run.json", {
        "started_at": run_started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "papers_fetched": len(papers),
        "new_papers": len(new_papers),
        "included": included_count,
        "pdf_errors": pdf_errors,
        "publish_success": success,
        "publish_message": message,
    })


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.getLogger("arxiv-feed").exception("run.py crashed")
        sys.exit(1)
