from source_globo_ads.streams.base import flatten


def test_flatten_underscores_one_level_of_nesting():
    rec = {
        "date": "2026-06-01",
        "codCampaing": "88398",
        "impression": {"impressionsDelivered": 10, "impressionsContracted": 12},
        "video": {"viewAll": 3, "vtr": 1},
        "investment": {"lineItem": 1.5, "campaign": None},
        "clicks": 2,
    }
    assert flatten(rec) == {
        "date": "2026-06-01",
        "codCampaing": "88398",
        "impression_impressionsDelivered": 10,
        "impression_impressionsContracted": 12,
        "video_viewAll": 3,
        "video_vtr": 1,
        "investment_lineItem": 1.5,
        "investment_campaign": None,
        "clicks": 2,
    }


def test_flatten_leaves_already_flat_records_alone():
    rec = {"date": "2026-06-01", "clicks": 2}
    assert flatten(rec) == rec
