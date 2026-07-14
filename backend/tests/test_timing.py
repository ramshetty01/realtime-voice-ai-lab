from app.timing import Timer


def test_timer_returns_milliseconds() -> None:
    assert Timer().ms() >= 0
