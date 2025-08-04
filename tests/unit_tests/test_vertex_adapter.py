from app.services.providers.vertex_adapter import VertexAdapter


def test_vertex_adapter_base_url_global():
    config = {"publisher": "anthropic", "location": "global"}
    adapter = VertexAdapter("vertex", None, config)
    assert adapter._base_url == "https://aiplatform.googleapis.com"


def test_vertex_adapter_base_url_region():
    config = {"publisher": "anthropic", "location": "us-east1"}
    adapter = VertexAdapter("vertex", None, config)
    assert adapter._base_url == "https://us-east1-aiplatform.googleapis.com" 