import pytest

from archetypeai import ArchetypeAI

def test_client_init():
    client = ArchetypeAI("fake_api_key")
    assert client