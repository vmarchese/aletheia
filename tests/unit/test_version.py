"""Test basic package setup and version."""
import aletheia


def test_version_exists() -> None:
    """Test that version is defined."""
    assert hasattr(aletheia, "__version__")
    assert aletheia.__version__ is not None


def test_version_format() -> None:
    """Test that version follows expected format."""
    version = aletheia.__version__
    assert isinstance(version, str)
    assert len(version.split(".")) >= 2
