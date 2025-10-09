import pytest

from archetypeai.api_client import ArchetypeAI

def test_client_init():
    client = ArchetypeAI("fake_api_key")
    assert client