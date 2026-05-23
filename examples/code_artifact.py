def normalize_scores(scores):
    """Return scores normalized to a 0-100 range."""
    if not scores:
        raise ValueError("scores cannot be empty")
    minimum = min(scores)
    maximum = max(scores)
    if minimum == maximum:
        return [100 for _ in scores]
    return [round(((score - minimum) / (maximum - minimum)) * 100) for score in scores]


def test_normalize_scores():
    assert normalize_scores([1, 2, 3]) == [0, 50, 100]
    assert normalize_scores([4, 4]) == [100, 100]
    try:
        normalize_scores([])
    except ValueError:
        pass
    else:
        raise AssertionError("empty input should fail")


# The implementation handles the main edge case where every input has the same
# value. The tradeoff is that it rounds to integers for UI clarity, which loses
# precision but makes feedback easier to read. The next step is to add type
# validation and document whether negative scores are allowed.
