from tg_vacancy_bot.models import Vacancy, canonical_identity_url


def make_vacancy(url: str | None) -> Vacancy:
    return Vacancy(
        title="Junior Frontend Developer",
        description="Hiring a junior frontend developer.",
        source="Test",
        url=url,
    )


def test_identity_source_matches_article_with_and_without_utm_parameters() -> None:
    base = make_vacancy("https://example.com/jobs/42?id=42")
    with_utm = make_vacancy(
        "https://example.com/jobs/42?utm_source=telegram&utm_campaign=digest&utm_term=feed&id=42"
    )

    assert with_utm.identity_source == base.identity_source


def test_identity_source_matches_trailing_slash_and_fragment_variants() -> None:
    base = make_vacancy("https://example.com/jobs/42")
    slashed = make_vacancy("https://example.com/jobs/42/")
    fragmented = make_vacancy("https://example.com/jobs/42#fragment")
    combined = make_vacancy("HTTPS://Example.COM/jobs/42/?fbclid=abc&gclid=def#top")

    assert slashed.identity_source == base.identity_source
    assert fragmented.identity_source == base.identity_source
    assert combined.identity_source == base.identity_source


def test_identity_source_keeps_distinct_paths_distinct() -> None:
    first = make_vacancy("https://example.com/jobs/42")
    second = make_vacancy("https://example.com/jobs/43")

    assert first.identity_source != second.identity_source


def test_identity_source_preserves_path_case() -> None:
    first = make_vacancy("https://example.com/Post/7")
    second = make_vacancy("https://example.com/post/7")

    assert first.identity_source != second.identity_source


def test_identity_source_falls_back_to_title_fingerprint_without_url() -> None:
    vacancy = Vacancy(title="Junior Frontend Developer", description="Hiring a junior frontend developer.", source="Test")

    assert vacancy.identity_source == "junior frontend developer|hiring a junior frontend developer."


def test_canonical_identity_url_passthrough_garbage_without_raising() -> None:
    assert canonical_identity_url("not a url at all") == "not a url at all"
    assert canonical_identity_url("  Some Messy Text //  ") == "some messy text //"
    assert canonical_identity_url("//example.com/no-scheme") == "//example.com/no-scheme"

    vacancy = make_vacancy("not a url at all")

    assert vacancy.identity_source == "not a url at all"


def test_canonical_identity_url_normalizes_scheme_host_and_tracking_query() -> None:
    assert canonical_identity_url("HTTPS://Example.COM/Post/?utm_source=x&id=7#frag") == "https://example.com/Post?id=7"


def test_canonical_identity_url_drops_query_marker_when_all_params_are_tracking() -> None:
    assert canonical_identity_url("https://example.com/a?utm_source=x#f") == "https://example.com/a"


def test_canonical_identity_url_keeps_non_tracking_params_in_order() -> None:
    assert (
        canonical_identity_url("https://example.com/a?keep=2&utm_medium=c&id=1&si=z")
        == "https://example.com/a?keep=2&id=1"
    )
