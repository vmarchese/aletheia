"""Unit tests for menu system."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from aletheia.ui.menu import Menu, MenuItem, create_menu


class TestMenuItem:
    """Tests for MenuItem class."""

    def test_menu_item_creation(self):
        """Test MenuItem initialization."""
        item = MenuItem("Test Label", "test_value", "Test description")

        assert item.label == "Test Label"
        assert item.value == "test_value"
        assert item.description == "Test description"

    def test_menu_item_without_description(self):
        """Test MenuItem without description."""
        item = MenuItem("Test Label", "test_value")

        assert item.label == "Test Label"
        assert item.value == "test_value"
        assert item.description is None


class TestMenu:
    """Tests for Menu class."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    @pytest.fixture
    def menu(self, mock_console):
        """Create Menu instance with mock console."""
        return Menu(mock_console)

    def test_menu_creation(self):
        """Test Menu initialization."""
        menu = Menu()
        assert menu.console is not None

    def test_menu_with_console(self, mock_console):
        """Test Menu with provided console."""
        menu = Menu(mock_console)
        assert menu.console == mock_console

    @patch('aletheia.ui.menu.Prompt.ask')
    def test_show_simple_menu(self, mock_ask, menu):
        """Test showing a simple menu."""
        mock_ask.return_value = "2"

        items = [
            MenuItem("Option 1", "value1"),
            MenuItem("Option 2", "value2"),
            MenuItem("Option 3", "value3")
        ]

        result = menu.show("Choose an option:", items)

        assert result == "value2"
        assert menu.console.print.called

    @patch('aletheia.ui.menu.Prompt.ask')
    def test_show_menu_with_default(self, mock_ask, menu):
        """Test menu with default selection."""
        mock_ask.return_value = "1"

        items = [
            MenuItem("Option 1", "value1"),
            MenuItem("Option 2", "value2")
        ]

        result = menu.show("Choose an option:", items, default=1)

        assert result == "value1"
        mock_ask.assert_called_once()

    @patch('aletheia.ui.menu.Prompt.ask')
    def test_show_menu_invalid_then_valid(self, mock_ask, menu):
        """Test menu with invalid input followed by valid input."""
        mock_ask.side_effect = ["5", "2"]  # Invalid then valid

        items = [
            MenuItem("Option 1", "value1"),
            MenuItem("Option 2", "value2")
        ]

        result = menu.show("Choose an option:", items)

        assert result == "value2"
        assert mock_ask.call_count == 2

    @patch('aletheia.ui.menu.Prompt.ask')
    def test_show_menu_with_back(self, mock_ask, menu):
        """Test menu with back option."""
        mock_ask.return_value = "0"

        items = [
            MenuItem("Option 1", "value1"),
            MenuItem("Option 2", "value2")
        ]

        result = menu.show("Choose an option:", items, allow_back=True)

        assert result is None

    def test_show_empty_menu_raises_error(self, menu):
        """Test that empty menu raises ValueError."""
        with pytest.raises(ValueError, match="Menu must have at least one item"):
            menu.show("Choose an option:", [])

    @patch('aletheia.ui.menu.Prompt.ask')
    def test_show_simple_string_menu(self, mock_ask, menu):
        """Test show_simple with string choices."""
        mock_ask.return_value = "2"

        result = menu.show_simple(
            "Choose an option:",
            ["Option 1", "Option 2", "Option 3"]
        )

        assert result == "Option 2"

    @patch('aletheia.ui.menu.Prompt.ask')
    def test_show_multiselect(self, mock_ask, menu):
        """Test multiselect menu."""
        mock_ask.return_value = "1,3"

        items = [
            MenuItem("Option 1", "value1"),
            MenuItem("Option 2", "value2"),
            MenuItem("Option 3", "value3")
        ]

        result = menu.show_multiselect("Select options:", items)

        assert result == ["value1", "value3"]

    @patch('aletheia.ui.menu.Prompt.ask')
    def test_show_multiselect_all(self, mock_ask, menu):
        """Test multiselect with 'all' selection."""
        mock_ask.return_value = "all"

        items = [
            MenuItem("Option 1", "value1"),
            MenuItem("Option 2", "value2"),
            MenuItem("Option 3", "value3")
        ]

        result = menu.show_multiselect("Select options:", items)

        assert result == ["value1", "value2", "value3"]

    @patch('aletheia.ui.menu.Prompt.ask')
    def test_show_multiselect_with_defaults(self, mock_ask, menu):
        """Test multiselect with default selections."""
        mock_ask.return_value = "1,2"

        items = [
            MenuItem("Option 1", "value1"),
            MenuItem("Option 2", "value2"),
            MenuItem("Option 3", "value3")
        ]

        result = menu.show_multiselect("Select options:", items, defaults=[1, 2])

        assert result == ["value1", "value2"]

    @patch('aletheia.ui.menu.Prompt.ask')
    def test_show_multiselect_invalid_choice(self, mock_ask, menu):
        """Test multiselect with invalid choice."""
        mock_ask.side_effect = ["1,5", "1,2"]  # Invalid then valid

        items = [
            MenuItem("Option 1", "value1"),
            MenuItem("Option 2", "value2")
        ]

        result = menu.show_multiselect("Select options:", items)

        assert result == ["value1", "value2"]
        assert mock_ask.call_count == 2

    def test_multiselect_empty_menu_raises_error(self, menu):
        """Test that empty multiselect menu raises ValueError."""
        with pytest.raises(ValueError, match="Menu must have at least one item"):
            menu.show_multiselect("Select options:", [])

    @patch('aletheia.ui.menu.Prompt.ask')
    def test_keyboard_interrupt_handling(self, mock_ask, menu):
        """Test handling of keyboard interrupt."""
        mock_ask.side_effect = KeyboardInterrupt()

        items = [MenuItem("Option 1", "value1")]

        with pytest.raises(KeyboardInterrupt):
            menu.show("Choose an option:", items)


def test_create_menu_factory():
    """Test create_menu factory function."""
    menu = create_menu()
    assert isinstance(menu, Menu)
    assert menu.console is not None
