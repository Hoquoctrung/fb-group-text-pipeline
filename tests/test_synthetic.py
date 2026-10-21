from fbpipe.collect.synthetic import SyntheticCollector


def test_synthetic_is_deterministic() -> None:
    first = [
        p.model_dump(mode="json")
        for p in SyntheticCollector(n=20, seed=42).iter_posts()
    ]
    second = [
        p.model_dump(mode="json")
        for p in SyntheticCollector(n=20, seed=42).iter_posts()
    ]
    assert first == second


def test_synthetic_count_and_labels() -> None:
    posts = list(SyntheticCollector(n=25, seed=42).iter_posts())
    assert len(posts) == 25
    assert all(post.source == "synthetic" for post in posts)
    assert all(post.group_id for post in posts)


def test_synthetic_contains_noise_fixture() -> None:
    texts = "\n".join(
        post.text for post in SyntheticCollector(n=100, seed=42).iter_posts()
    )
    assert "😊" in texts
    assert "http" in texts
    assert "@" in texts
    assert "#python" in texts
