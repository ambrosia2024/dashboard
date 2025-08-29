# api_test/scio/model_insights.py

import django
import os
import pandas as pd
import sys

from dotenv import load_dotenv
from openai import OpenAI

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir


while not os.path.isfile(os.path.join(project_root, 'manage.py')):
    parent = os.path.dirname(project_root)
    if parent == project_root:  # reached filesystem root
        raise FileNotFoundError("manage.py not found. Ensure this script is inside a Django project.")
    project_root = parent

sys.path.append(project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

load_dotenv()
load_dotenv(os.path.join(project_root, ".env"))

df = pd.read_csv("all_models.csv")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_pathogen_openai(name: str) -> str:
    prompt = f"""
    Extract the pathogen name (e.g., Salmonella, Campylobacter jejuni, Listeria monocytogenes, E. coli O157:H7, Taenia solium)
    from this model title. If no pathogen is mentioned, return "None".

    Model name: "{name}"
    Pathogen:"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"ERROR: {e}"

# Apply GPT extraction
df["pathogen"] = df["name"].apply(extract_pathogen_openai)

# Save enriched dataset
df.to_csv("all_models_with_pathogens_ai.csv", index=False)

# Summarise
summary = df["pathogen"].value_counts().reset_index()
summary.columns = ["pathogen", "count"]
summary.to_csv("pathogen_summary_ai.csv", index=False)

print(summary.head(20))
