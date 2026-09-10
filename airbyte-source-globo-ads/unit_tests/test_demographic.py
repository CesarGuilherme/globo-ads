from source_globo_ads.auth import BareTokenAuthenticator
from source_globo_ads.streams.demographic import (
    DigitalDemographic,
    explode_demographic,
    select_demographic_candidates,
)
from source_globo_ads.streams.items import DigitalItems


def test_candidate_items_stream_does_not_need_cdk_authenticator_attr():
    """CDK 7 HttpStream never sets .authenticator; production died on AttributeError."""
    auth = BareTokenAuthenticator("tok")
    demo = DigitalDemographic(authenticator=auth, cod_client=258469)
    assert not hasattr(demo, "authenticator")
    probe = demo._candidate_items_stream()
    assert isinstance(probe, DigitalItems)


def test_select_skips_dai_a_and_campaigns_older_than_cutoff():
    rows = [
        {"codCampaing": "1", "campaign": "Keep", "campaignType": "Display", "date": "2026-05-01"},
        {"codCampaing": "2", "campaign": "DAI", "campaignType": "DAI-A", "date": "2026-05-01"},
        {"codCampaing": "3", "campaign": "Old", "campaignType": "Display", "date": "2025-01-01"},
        {"codCampaing": "1", "campaign": "Keep", "campaignType": "Display", "date": "2026-04-01"},
    ]
    assert select_demographic_candidates(rows, cutoff="2026-01-01") == [("1", "Keep")]


def test_explode_unions_ages_genders_region_with_parent_fields():
    entry = {
        "startDate": "2026-01-01",
        "endDate": "2026-01-31",
        "codCampaign": "88398",
        "campaign": "Foo",
        "project": "P",
        "codClient": 258469,
        "nameClient": "SECOM",
        "codAgency": 1,
        "nameAgency": "A",
        "ages": [{"profileDomain": "Faixa Etaria", "label": "18-24", "impressions": 10.5}],
        "genders": [{"profileDomain": "Genero", "label": "M", "impressions": 40.0}],
        "region": [],
        "interests": [{"label": "ignored"}],
    }
    rows = explode_demographic(entry)
    assert len(rows) == 2
    assert rows[0]["codCampaign"] == "88398"
    assert rows[0]["label"] == "18-24"
    assert rows[1]["label"] == "M"
    assert "interests" not in rows[0]
