import pandas as pd

df = pd.read_csv("all_models.csv")

keywords = ["Listeria", "monocytogenes", "growth", "iceberg", "lettuce"]

def keyword_score(name, keywords):
    if pd.isna(name):
        return 0
    text = name.lower()
    return sum(1 for kw in keywords if kw.lower() in text)

# Apply scoring
df["keyword_matches"] = df["name"].apply(lambda x: keyword_score(x, keywords))

# Sort by number of matches
ranked = df.sort_values("keyword_matches", ascending=False)

# Show top 10
print(ranked[["name", "keyword_matches"]].head(10))
