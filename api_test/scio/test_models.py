# api_test/scio/test_models.py

import argparse
import os
import re
import requests

from dotenv import load_dotenv
import pandas as pd
from utils import print_model_info

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL")
ENDPOINT = os.getenv("GET_MODELS_ENDPOINT")

def filter_models(models, name_filter=None, max_ram=None, gpu_only=False):
    filtered = []
    for model in models:
        if name_filter and name_filter.lower() not in model.get("name", "").lower():
            continue
        if gpu_only and model.get("gpu_count_required", 0) == 0:
            continue
        if max_ram is not None and model.get("ram_gb_required", 0) > max_ram:
            continue
        filtered.append(model)
    return filtered

def main():
    parser = argparse.ArgumentParser(description="Filter Ambrosia models.")
    parser.add_argument("--name", help="Filter by name substring (case-insensitive)")
    parser.add_argument("--max-ram", type=float, help="Max RAM (in GB)")
    parser.add_argument("--gpu", action="store_true", help="Only show GPU-based models")
    args = parser.parse_args()

    url = BASE_URL + ENDPOINT
    print(f"Testing: {url}")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict) and 'models' in data:
            models = filter_models(data["models"], args.name, args.max_ram, args.gpu)

            print_model_info(models, "Filtered Ambrosia Models")

            df = pd.DataFrame([
                {"id": m.get("id") or m.get("model_id") or m.get("uuid"), "name": m.get("name", "")}
                for m in models
            ])

            df["name_norm"] = df["name"].str.strip()

            # Buckets by prefix
            df["bucket"] = "Other"
            df.loc[df["name_norm"].str.startswith("Gropin secondary growth model",
                                                  na=False), "bucket"] = "Gropin secondary growth model"
            # Note: put the more specific rule above so it doesn't get swallowed by this one
            df.loc[(df["bucket"] == "Other") & df["name_norm"].str.startswith("Gropin secondary",
                                                                              na=False), "bucket"] = "Gropin secondary"
            df.loc[(df["bucket"] == "Other") & df["name_norm"].str.startswith("Gropin", na=False), "bucket"] = "Gropin"

            # Regex to extract pathogen, matrix and gropin_id for the canonical pattern, e.g.:
            # "Gropin secondary growth model for Escherichia coli O157:H7 in/on Tryptic Soy Broth (gropin ID: 1463 )"
            pat = re.compile(
                r"^Gropin\s+secondary(?:\s+growth)?\s+model\s+for\s+(?P<pathogen>.*?)\s+in/on\s+(?P<matrix>.*?)\s*\(gropin ID:\s*(?P<gropin_id>\d+)\s*\)\s*$"
            )

            def _extract(row):
                m = pat.match(row["name_norm"])
                if not m:
                    return pd.Series({"pathogen": None, "matrix": None, "gropin_id": None})
                return pd.Series({
                    "pathogen": m.group("pathogen"),
                    "matrix": m.group("matrix"),
                    "gropin_id": int(m.group("gropin_id"))
                })

            df[["pathogen", "matrix", "gropin_id"]] = df.apply(_extract, axis=1)

            # ---- Console summaries ----
            print("\n=== Buckets (by name prefix) ===")
            bucket_counts = df["bucket"].value_counts(dropna=False).sort_index()
            for k, v in bucket_counts.items():
                print(f"{k}: {v}")

            print("\n=== Distinct pathogens found (from canonical 'Gropin ... for X in/on Y' pattern) ===")
            pathogen_counts = df["pathogen"].dropna().value_counts().sort_values(ascending=False)
            print(f"Unique pathogens: {pathogen_counts.shape[0]}")
            print(pathogen_counts.head(20))

            print("\n=== Examples of non-Gropin or unmatched names ===")
            unmatched = df[df["pathogen"].isna()].head(10)[["id", "name"]]
            for _, r in unmatched.iterrows():
                print(f"- {r['name']} (id: {r['id']})")

            # ---- Persist results ----
            csv_path = f"model_pathogen_counts.csv"
            txt_path = f"model_name_summary.txt"

            # CSV: pathogen frequency (good for later filtering/joins)
            pathogen_counts.rename_axis("pathogen").reset_index(name="count").to_csv(csv_path, index=False)

            # TXT: compact human-readable summary
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("=== Buckets (by name prefix) ===\n")
                for k, v in bucket_counts.items():
                    f.write(f"{k}: {v}\n")

                f.write("\n=== Pathogen counts (canonical pattern only) ===\n")
                f.write(f"Unique pathogens: {pathogen_counts.shape[0]}\n")
                for pathogen, cnt in pathogen_counts.items():
                    f.write(f"{pathogen}: {cnt}\n")

                f.write("\n=== First 20 examples of parsed entries ===\n")
                for _, r in df.dropna(subset=["pathogen"]).head(20)[
                    ["id", "name", "pathogen", "matrix", "gropin_id"]].iterrows():
                    f.write(
                        f"- {r['name']} | pathogen={r['pathogen']} | matrix={r['matrix']} | gropin_id={r['gropin_id']} | id={r['id']}\n")

            print(f"\nSaved pathogen counts CSV -> {csv_path}")
            print(f"Saved text summary       -> {txt_path}")
            # --- end of analysis block ---

            # 2) File: write ONLY ID and Name (no CPU/GPU/RAM/Image/FSKX)
            out_file = f"filtered_models.txt"

            lines = []
            for idx, m in enumerate(models, start=1):
                model_id = (
                        m.get("id")
                        or m.get("model_id")
                        or m.get("uuid")
                        or m.get("ID")
                        or "N/A"
                )
                name = m.get("name", "N/A")
                # Keep formatting simple and readable
                lines.append(
                    f"Model {idx}:\n"
                    f"  ID   : {model_id}\n"
                    f"  Name : {name}\n"
                )

            if not lines:
                lines.append("No models matched the given filters.\n")

            with open(out_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            print(f"Minimal report (ID + Name only) saved to: {out_file}")

            # --- Write ALL models (grouped by bucket) into a text file ---
            all_file = f"all_models_grouped.txt"

            with open(all_file, "w", encoding="utf-8") as f:
                for bucket in sorted(df["bucket"].unique()):
                    f.write(f"=== {bucket} ===\n")
                    group = df[df["bucket"] == bucket]
                    for idx, row in enumerate(group.itertuples(index=False), start=1):
                        f.write(f"Model {idx}:\n")
                        f.write(f"  ID   : {row.id}\n")
                        f.write(f"  Name : {row.name}\n\n")

            print(f"Full grouped model list saved to: {all_file}")

        else:
            print("Unexpected response format:")
            print(data)

    except requests.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    main()
