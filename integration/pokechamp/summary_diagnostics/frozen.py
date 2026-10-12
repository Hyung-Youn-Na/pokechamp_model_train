"""Subprocess entry: import ONLY EX-020 archived parent code to reconstruct H0."""

import json
import sys
import types
from pathlib import Path


def main():
    archive, workspace, battles = map(Path, sys.argv[1:4])
    # The archive omitted integration/__init__.py. Install its namespace explicitly;
    # never allow a current parent module to satisfy an archived relative import.
    package = types.ModuleType("integration")
    package.__path__ = [str(archive / "integration")]
    sys.modules["integration"] = package
    sys.path.insert(0, str(workspace / "pokechamp"))
    from integration.pokechamp import constants

    # Relocate workspace resources; source/normalization/prompt code stays archived.
    constants.WORKSPACE_ROOT = workspace
    constants.POKECHAMP_ROOT = workspace / "pokechamp"
    constants.SHOWDOWN_ROOT = workspace / "pokemon-showdown"
    from integration.pokechamp.improved_io.cloud_gate import (
        PROMPTS,
        summary_boundaries,
        summary_context,
    )

    rows = []
    for name in json.loads(sys.stdin.read()):
        bundle = battles / name
        boundary = summary_boundaries(bundle)[0]
        context = summary_context(bundle, boundary)
        rows.append(
            dict(
                bundle=str(bundle),
                cutoff=boundary,
                context=context,
                user_prompt=json.dumps(context, ensure_ascii=False),
            )
        )
    Path(sys.argv[4]).write_text(
        json.dumps(dict(system_prompt=(PROMPTS / "summary.txt").read_text(), scenes=rows))
    )


if __name__ == "__main__":
    main()
