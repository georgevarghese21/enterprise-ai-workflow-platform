from app.models.policy_chunk import PolicyChunk
from app.rag.chunking import chunk_markdown
from app.rag.embeddings import MockHashingEmbeddingProvider


def test_chunk_markdown_splits_by_heading():
    text = "# Title\n\n## Section One\n\nContent one.\n\n## Section Two\n\nContent two.\n"
    chunks = chunk_markdown(text)
    assert [c.title for c in chunks] == ["Section One", "Section Two"]
    assert chunks[0].content == "Content one."
    assert chunks[1].content == "Content two."


def test_mock_embedding_is_deterministic():
    provider = MockHashingEmbeddingProvider()
    assert provider.embed("laptop request") == provider.embed("laptop request")


def test_mock_embedding_favors_shared_vocabulary():
    provider = MockHashingEmbeddingProvider()
    a = provider.embed("request a new laptop from IT")
    b = provider.embed("I need a laptop from the IT team")
    c = provider.embed("book a flight for a client visit")

    def cosine(x: list[float], y: list[float]) -> float:
        return sum(xi * yi for xi, yi in zip(x, y, strict=True))

    assert cosine(a, b) > cosine(a, c)


def test_policy_search_endpoint_returns_relevant_chunk(client, db_session):
    provider = MockHashingEmbeddingProvider()
    laptop_chunk = PolicyChunk(
        document_name="it-equipment-and-software-policy.md",
        title="Standard equipment requests",
        chunk_index=0,
        content="New employees are issued a standard laptop during onboarding.",
        embedding=provider.embed("laptop equipment onboarding IT"),
    )
    travel_chunk = PolicyChunk(
        document_name="travel-and-expense-policy.md",
        title="Booking business travel",
        chunk_index=0,
        content="Domestic flights and hotels may be booked through the travel portal.",
        embedding=provider.embed("flight hotel travel booking"),
    )
    db_session.add_all([laptop_chunk, travel_chunk])
    db_session.commit()

    response = client.post("/api/policy/search", json={"query": "I need a new laptop", "top_k": 1})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["chunk"]["document_name"] == "it-equipment-and-software-policy.md"


def test_list_policy_documents_groups_by_document(client, db_session):
    provider = MockHashingEmbeddingProvider()
    db_session.add_all(
        [
            PolicyChunk(
                document_name="it-equipment-and-software-policy.md",
                title="Standard equipment requests",
                chunk_index=0,
                content="Chunk one.",
                embedding=provider.embed("chunk one"),
            ),
            PolicyChunk(
                document_name="it-equipment-and-software-policy.md",
                title="Software licenses",
                chunk_index=1,
                content="Chunk two.",
                embedding=provider.embed("chunk two"),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/policy/documents")
    assert response.status_code == 200
    body = response.json()
    assert body == [
        {"document_name": "it-equipment-and-software-policy.md", "chunk_count": 2}
    ]
