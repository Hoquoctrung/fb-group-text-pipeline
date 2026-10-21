"""Print text_clean after each S1-S7 transform for a Vietnamese regression phrase."""

from pathlib import Path
from typing import Any

from fbpipe.preprocess.steps import build_transforms

TEXT = "chia sẻ thông tin về mọi người"


def main() -> None:
    transforms, _ = build_transforms(
        Path("resources"),
        english_words=set(),
        load_english_reference=False,
    )
    for transform in transforms[1:8]:
        # Give every transform the same original input to isolate its behavior.
        doc: dict[str, Any] = {"text_raw": TEXT, "text_clean": TEXT}
        doc = transform.apply(doc)
        print(f"{transform.name}: {doc['text_clean']!r}")


if __name__ == "__main__":
    main()
