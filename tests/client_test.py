from archetypeai import ArchetypeAI


def test_client_init():
    client = ArchetypeAI("fake_api_key")
    assert client


def test_agents_api_init():
    client = ArchetypeAI("fake_api_key")
    assert client.agents.blueprints
    assert client.agents.bundles
    assert client.agents.instances
    assert callable(client.agents.bundles.create)
    assert callable(client.agents.bundles.delete)
    assert callable(client.agents.bundles.run)
