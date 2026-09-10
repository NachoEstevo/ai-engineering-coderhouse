def test_settings_use_safe_defaults_and_hide_secrets():
    from config import Settings

    settings = Settings(
        pinecone_api_key="pinecone-secret",
        openai_api_key="openai-secret",
        index_name="asyncio-rag-test",
    )

    assert settings.embedding_dimension == 1536
    assert settings.namespace == "asyncio-docs"
    assert settings.top_k == 5
    assert "pinecone-secret" not in repr(settings)
    assert "openai-secret" not in repr(settings)
