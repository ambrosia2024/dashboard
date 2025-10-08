import logging
import time
import hashlib

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from lumenix.models import CropMaster

# SPARQL client for AGROVOC
from SPARQLWrapper import SPARQLWrapper, JSON

ENDPOINT = "https://agrovoc.fao.org/sparql"  # FAO's public SPARQL endpoint

PREFIXES = "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"

def _select_with_where(select_vars: str, where_body: str, graph: str | None) -> str:
    """Builds a SELECT…WHERE…; if graph is provided, inserts GRAPH <graph> { … }."""
    if graph:
        return PREFIXES + f"SELECT {select_vars} WHERE {{ GRAPH <{graph}> {{ {where_body} }} }}"
    return PREFIXES + f"SELECT {select_vars} WHERE {{ {where_body} }}"

def _notation_from_uri(uri: str) -> str:
    # Extract 'c_12151' from 'http://aims.fao.org/aos/agrovoc/c_12151'
    return uri.rsplit("/", 1)[-1]

def _run_sparql(query: str, *, endpoint: str, label: str, timeout: int, retries: int, retry_wait: float, debug: bool = False):
    """
    Execute a SPARQL SELECT with timing, retries and structured logs.
    `label` is a short human-readable tag (e.g., 'all_concepts page 0').
    """
    logger = logging.getLogger("agrovoc")
    # Short query fingerprint (to avoid logging huge bodies at INFO)
    qhash = hashlib.sha1(query.encode("utf-8")).hexdigest()[:10]

    for attempt in range(1, retries + 1):
        start = time.perf_counter()
        try:
            s = SPARQLWrapper(endpoint)
            s.setMethod("POST")               # safer for large queries
            s.setReturnFormat(JSON)
            s.setQuery(query)
            s.setTimeout(timeout)
            s.addCustomHttpHeader("User-Agent", "AmbrosiaDashboard/1.0 (+https://ambrosia-project.eu)")
            logger.info("SPARQL %s | attempt=%d/%d | timeout=%ss | qhash=%s",
                        label, attempt, retries, timeout, qhash)
            if debug:
                logger.debug("SPARQL QUERY (%s):\n%s", label, query)

            res = s.query()                   # network call
            elapsed = time.perf_counter() - start
            data = res.convert()
            rows = data["results"]["bindings"]
            logger.info("SPARQL %s | OK in %.2fs | rows=%d", label, elapsed, len(rows))
            return rows

        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.warning("SPARQL %s | FAIL in %.2fs | %s | attempt %d/%d",
                           label, elapsed, repr(e), attempt, retries)
            if attempt >= retries:
                # Bubble up the last exception after logging
                raise
            sleep_for = retry_wait * (2 ** (attempt - 1))
            logger.info("SPARQL %s | retrying in %.2fs ...", label, sleep_for)
            time.sleep(sleep_for)

def find_by_label(label: str, lang: str = "en", *, timeout: int, retries: int, retry_wait: float, debug: bool = False):
    """Find exact label match in a given language. Returns list of (uri, prefLabel, notation)."""
    q = f"""
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?concept ?prefLabel ?notation WHERE {{
      ?concept a skos:Concept ; skos:prefLabel ?prefLabel .
      FILTER (LANG(?prefLabel) = "{lang}")
      FILTER (LCASE(STR(?prefLabel)) = "{label.lower()}")
      OPTIONAL {{ ?concept skos:notation ?notation }}
    }}
    LIMIT 100
    """
    rows = _run_sparql(q, label=f"find_by_label {label} ({lang})",
                       timeout=timeout, retries=retries, retry_wait=retry_wait, debug=debug)
    out = []
    for r in rows:
        uri = r["concept"]["value"]
        pref = r["prefLabel"]["value"]
        notation = r.get("notation", {}).get("value") or _notation_from_uri(uri)
        out.append((uri, pref, notation))
    return out

def children_of(parent_uri: str, lang: str = "en", *, timeout: int, retries: int, retry_wait: float, debug: bool = False):
    """Get all narrower concepts under a parent. Returns list of (uri, prefLabel, notation)."""
    q = f"""
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?child ?label ?notation WHERE {{
      ?child skos:broader <{parent_uri}> ;
             skos:prefLabel ?label .
      FILTER (LANG(?label) = "{lang}")
      OPTIONAL {{ ?child skos:notation ?notation }}
    }}
    ORDER BY LCASE(STR(?label))
    """
    rows = _run_sparql(q, label=f"children_of {parent_uri}",
                       timeout=timeout, retries=retries, retry_wait=retry_wait, debug=debug)
    out = []
    for r in rows:
        uri = r["child"]["value"]
        pref = r["label"]["value"]
        notation = r.get("notation", {}).get("value") or _notation_from_uri(uri)
        out.append((uri, pref, notation))
    return out

def all_concepts(lang: str = "en", page_size: int = 1000, max_rows: int = 5000,
                 *, timeout: int, retries: int, retry_wait: float, debug: bool = False):
    """
    Iterate through ALL AGROVOC concepts with an English label (paged).
    Yields (uri, label, notation).
    """
    logger = logging.getLogger("agrovoc")
    fetched = 0
    offset = 0
    while True:
        label = f"all_concepts offset={offset} limit={page_size}"
        q = f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?concept ?label ?notation WHERE {{
          ?concept a skos:Concept ;
                   skos:inScheme <http://aims.fao.org/aos/agrovoc> ;
                   skos:prefLabel ?label .
          FILTER (LANG(?label) = "{lang}")
          OPTIONAL {{ ?concept skos:notation ?notation }}
        }}
        ORDER BY LCASE(STR(?label))
        LIMIT {page_size} OFFSET {offset}
        """
        page_rows = _run_sparql(q, label=label, timeout=timeout, retries=retries,
                                retry_wait=retry_wait, debug=debug)
        if not page_rows:
            logger.info("No more rows after offset=%d.", offset)
            break

        # Transform + yield
        for r in page_rows:
            uri = r["concept"]["value"]
            lab = r["label"]["value"]
            notation = r.get("notation", {}).get("value") or _notation_from_uri(uri)
            yield (uri, lab, notation)
            fetched += 1
            if max_rows != -1 and fetched >= max_rows:
                logger.info("Hit max_rows=%d; stopping.", max_rows)
                return

        offset += page_size
        time.sleep(retry_wait if retry_wait > 0 else 0.5)

def _print_table(rows):
    """Pretty print to console without saving (dry-run)."""
    if not rows:
        print("No rows.")
        return
    # Simple fixed-width table
    print(f"{'AGROVOC ID':<12}  {'Label':<40}  {'URI'}")
    print("-" * 100)
    for uri, label, notation in rows:
        print(f"{notation:<12}  {label[:40]:<40}  {uri}")

class Command(BaseCommand):
    help = "Fetch AGROVOC concepts by label or by parent (narrower). Dry-run by default; use --save to persist."

    def add_arguments(self, parser):
            parser.add_argument("--label", help="Exact English label (e.g., 'eggplant').")
            parser.add_argument("--parent-uri", help="Parent concept URI to import its narrower children.")
            parser.add_argument("--lang", default="en", help="Language code for labels (default: en).")
            parser.add_argument("--save", action="store_true", help="Persist to DB instead of printing.")
            parser.add_argument("--active", action="store_true", help="Mark saved rows as Active (status=1).")
            parser.add_argument("--all", action="store_true", help="List ALL AGROVOC concepts (English labels) in pages (no DB writes unless --save).")
            parser.add_argument("--page-size", type=int, default=1000, help="Rows per SPARQL page (default: 1000).")
            parser.add_argument("--max-rows", type=int, default=5000, help="Safety cap to avoid huge downloads (default: 5000). Use -1 for no cap (not recommended).")

            parser.add_argument("--verbose", action="store_true", help="INFO level logging to stdout.")
            parser.add_argument("--debug", action="store_true", help="DEBUG level logging (logs full queries).")
            parser.add_argument("--log-file", help="Optional path to write logs to a file.")

            parser.add_argument("--page-size", type=int, default=200, help="Rows per SPARQL page (default: 200).")
            parser.add_argument("--timeout", type=int, default=90, help="HTTP timeout (seconds) per SPARQL call. Default: 90.")
            parser.add_argument("--retries", type=int, default=5, help="Number of retry attempts on failure. Default: 5.")
            parser.add_argument("--retry-wait", type=float, default=1.5, help="Initial backoff (seconds). Doubles each retry.")
            parser.add_argument("--throttle", type=float, default=0.5, help="Sleep seconds between page requests (default: 0.5s).")

    def handle(self, *args, **opts):
        # --- logging setup ---
        level = logging.WARNING
        if opts.get("verbose"):
            level = logging.INFO
        if opts.get("debug"):
            level = logging.DEBUG

        handlers = [logging.StreamHandler()]
        if opts.get("log_file"):
            handlers.append(logging.FileHandler(opts["log_file"]))

        logging.basicConfig(
            level=level,
            format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            handlers=handlers,
        )
        logger = logging.getLogger("agrovoc")
        logger.info("Starting get_crops_agrovoc (timeout=%ss, retries=%d, retry_wait=%ss)",
                    opts["timeout"], opts["retries"], opts["retry_wait"])

        label = opts.get("label")
        parent = opts.get("parent_uri")
        lang = opts["lang"]

        if not any([opts.get("all"), label, parent]):
            opts["all"] = True

        common = dict(timeout=opts["timeout"], retries=opts["retries"],
                      retry_wait=opts["retry_wait"], debug=opts["debug"])

        if opts.get("all"):
            rows = list(all_concepts(
                lang=opts["lang"], page_size=opts["page_size"], max_rows=opts["max_rows"], **common
            ))
        elif label:
            rows = find_by_label(label, opts["lang"], **common)
        else:
            rows = children_of(parent, opts["lang"], **common)

        # 1) Fetch
        # if opts.get("all"):
        #     # Stream to a list so _print_table() can show a total at the end.
        #     rows = list(all_concepts(
        #         lang=opts["lang"],
        #         page_size=opts["page_size"],
        #         max_rows=opts["max_rows"],
        #     ))
        # elif opts.get("label"):
        #     rows = find_by_label(opts["label"], opts["lang"])
        # elif opts.get("parent_uri"):
        #     rows = children_of(opts["parent_uri"], opts["lang"])
        # else:
        #     # Default to --all if nothing else given (safe-capped by --max-rows)
        #     rows = list(all_concepts(
        #         lang=opts["lang"],
        #         page_size=opts["page_size"],
        #         max_rows=opts["max_rows"],
        #     ))

        # 2) Dry-run print if not saving
        if not opts["save"]:
            self.stdout.write(self.style.WARNING("Dry-run (no DB writes). Showing fetched rows:\n"))
            _print_table(rows)
            self.stdout.write(self.style.SUCCESS(f"\nTotal: {len(rows)}"))
            return

        # 3) Save to DB (idempotent on agrovoc_uri)
        created, updated = 0, 0
        status_val = 1 if opts["active"] else 0
        with transaction.atomic():
            for uri, label_text, notation in rows:
                obj, is_new = CropMaster.objects.get_or_create(
                    agrovoc_uri=uri,
                    defaults={
                        "crop_name": label_text,
                        "agrovoc_notation": notation,
                        "status": status_val,
                    },
                )
                if is_new:
                    created += 1
                else:
                    changed = False
                    if obj.crop_name != label_text:
                        obj.crop_name = label_text
                        changed = True
                    if obj.agrovoc_notation != notation:
                        obj.agrovoc_notation = notation
                        changed = True
                    if obj.status != status_val:
                        obj.status = status_val
                        changed = True
                    if changed:
                        obj.save()
                        updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Saved {len(rows)} rows. Created={created}, Updated={updated}."
        ))