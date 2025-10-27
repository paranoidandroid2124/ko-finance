from datetime import date

from services.aggregation.timeline_metrics import build_timeline_series


def test_build_timeline_series_downsamples():
    raw_points = [
        {"date": date(2025, 1, 1), "sentiment_z": 0.1, "price_close": 100.0, "volume": 1200},
        {"date": date(2025, 1, 2), "sentiment_z": 0.2, "price_close": 101.0, "volume": 1300},
        {"date": date(2025, 1, 3), "sentiment_z": 0.3, "price_close": 102.0, "volume": 1400},
    ]
    series = build_timeline_series(raw_points, max_points=2)
    assert series["total_points"] == 3
    assert series["downsampled_points"] == 2
    assert series["points"][0]["date"] == date(2025, 1, 1)
    assert series["points"][-1]["date"] == date(2025, 1, 3)


def test_build_timeline_series_filters_bad_entries():
    raw_points = [
        {"date": "2025-01-01", "sentiment_z": 0.1},
        {"date": "invalid"},
        {"computed_for": "2025-01-03T00:00:00Z", "sentiment_z": -0.2},
    ]
    series = build_timeline_series(raw_points, max_points=365)
    assert series["total_points"] == 2
    assert all(point["date"] in {date(2025, 1, 1), date(2025, 1, 3)} for point in series["points"])
