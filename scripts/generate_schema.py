"""Export the validated Pydantic contract for TypeScript and integration checks."""

import json
from pathlib import Path

from separator_engine.schema import Contract

root = Path(__file__).resolve().parents[1]
dest = root / "packages" / "shared" / "schema.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(Contract.model_json_schema(mode="serialization"), indent=2) + "\n")
