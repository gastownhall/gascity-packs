from slugger import slugify


def test_slugify_basic_phrase() -> None:
    assert slugify("Hello, World!") == "hello-world"


def test_slugify_collapses_separators() -> None:
    assert slugify("  Multiple---spaces___OK  ") == "multiple-spaces-ok"


def test_slugify_handles_no_alphanumerics() -> None:
    assert slugify("!!!") == ""
