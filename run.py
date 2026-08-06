#!/usr/bin/env python3
"""Entrypoint: fetch arxiv -> dedupe -> judge via local LLM -> render feed -> publish."""
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import yaml

from lib import arxiv_fetch, classifier, publish, render, store

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


def classify_one(profile_text, paper, host, model):
    relevant, reason = classifier.classify(profile_text, paper["title"], paper["abstract"], host, model)
    return paper, relevant, reason


def main():
    config = load_config()
    paths = config["paths"]
    setup_logging(REPO_DIR / paths["log_file"])
    log = logging.getLogger("arxiv-feed")
    log.info("=== run start ===")

    profile_text = (REPO_DIR / paths["interest_profile"]).read_text(encoding="utf-8")

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

    host = config["ollama"]["host"]
    model = config["ollama"]["model"]
    max_workers = config["ollama"].get("max_workers", 4)
    window_size = config["feed"]["window_size"]

    relevant_count = 0
    if new_papers:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(classify_one, profile_text, paper, host, model) for paper in new_papers]
            for future in as_completed(futures):
                try:
                    paper, relevant, reason = future.result()
                except Exception as exc:  # noqa: BLE001 - fail closed, retried automatically next run
                    log.warning("classification failed, leaving unseen for retry next run: %s", exc)
                    continue

                judged_at = datetime.now(timezone.utc).isoformat()
                store.record_seen(seen_ids, paper["arxiv_id"], relevant, judged_at)
                if relevant:
                    relevant_count += 1
                    item = {**paper, "judged_at": judged_at, "reason": reason}
                    published_items = store.add_relevant_item(published_items, item, window_size)

    log.info("%d of %d new papers judged relevant", relevant_count, len(new_papers))

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
        str(REPO_DIR), paths["feed_output"], f"update feed: {relevant_count} new relevant papers"
    )
    log.log(logging.INFO if success else logging.ERROR, "publish: %s", message)

    log.info("=== run end ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.getLogger("arxiv-feed").exception("run.py crashed")
        sys.exit(1)
