import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from archetypeai.api_client import ArchetypeAI

def test_client_init():
    client = ArchetypeAI("fake_api_key")
    assert client