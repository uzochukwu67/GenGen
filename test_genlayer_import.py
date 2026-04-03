#!/usr/bin/env python3

"""
Test script to find the correct genlayer client import
"""

def test_imports():
    print("Testing genlayer imports...")

    try:
        import genlayer
        print("✅ genlayer imported successfully")
        print("Available attributes:", [x for x in dir(genlayer) if not x.startswith('_')])

        # Try different client imports
        try:
            from genlayer import Client
            print("✅ from genlayer import Client works")
        except ImportError as e:
            print("❌ from genlayer import Client failed:", e)

        try:
            from genlayer.client import Client
            print("✅ from genlayer.client import Client works")
        except ImportError as e:
            print("❌ from genlayer.client import Client failed:", e)

        try:
            import genlayer as gl
            client = gl.Client()
            print("✅ gl.Client() works")
        except Exception as e:
            print("❌ gl.Client() failed:", e)

        try:
            from genlayer import GenLayerClient
            print("✅ from genlayer import GenLayerClient works")
        except ImportError as e:
            print("❌ from genlayer import GenLayerClient failed:", e)

    except ImportError as e:
        print("❌ genlayer import failed:", e)

if __name__ == "__main__":
    test_imports()