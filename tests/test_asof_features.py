from cwt_sentiment.features import MODEL_FEATURES


def test_retrospective_inputs_exclude_collection_time_telemetry():
    unsafe = {"post_sentiment_weighted", "engagement_log", "engagement_total", "followers_mean"}
    assert unsafe.isdisjoint(MODEL_FEATURES)
