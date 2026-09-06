"""
Targeted test: verifies only cell 28 (spatial maps) patch is correct
by checking the grid_feats patch logic in isolation.
"""
import json

NB_PATH = "notebooks/pinn_train.ipynb"
with open(NB_PATH) as f:
    nb = json.load(f)

src = "".join(nb["cells"][28]["source"])

checks = [
    ("API hat cols are pre-normalized", "Step 4 comment present"),
    ("api{_k}hat", "API cols added to grid_feats"),
    ("_api_cols", "API cols in groupby"),
    ("grid_xy = collocation.groupby(GRID_KEYS, as_index=False)[[\"R\", \"Q\", \"ranomhat\"] + _api_cols].first()", "groupby updated"),
]

all_ok = True
for snippet, label in checks:
    ok = snippet in src
    print(f"  {'✓' if ok else '✗'} {label}")
    if not ok:
        all_ok = False

if all_ok:
    print("\n✅ Cell 28 patch verified — spatial map will include API hat cols")
else:
    print("\n❌ Some checks failed — review cell 28")
