import os
import subprocess
import time

from pathlib import Path
from typing import Iterable


from textual import on
from textual.binding import Binding
from textual.app import App, ComposeResult
from textual.containers import Container   
from textual.widgets import DirectoryTree, Footer, Header, Label, Input

""" 
editor name or path to it 
second value is fallback; try notepad++ or vim or whatever you like.
"""
EDITOR = os.environ.get('EDITOR', 'notepad')


def display_time() -> str:
    return str(time.strftime('%H:%M:%S'))


class PathInput(Input):
    """Custom Input widget for path entry with escape key support."""
    BINDINGS = [
        Binding("enter", "submit", "Submit"),
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def action_cancel(self) -> None:
        """Cancel the path input without changing the root."""
        tree = self.app.query_one('#tree', FilteredDirectoryTree)
        self.display = False
        tree.disabled = False
        tree.focus()
        


class FilteredDirectoryTree(DirectoryTree):
    dotfiles = False
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return paths if self.dotfiles else [path for path in paths if not path.name.startswith(".")]

    BINDINGS = [
        Binding("a", "toggle_dotfiles", "Toggle dotfiles"),
        Binding("e", "edit_file", "Edit file"),
        Binding("left", "cursor_left", "Collapse/To parent", show=False),
        Binding("right", "select_cursor", "Run", show=False),
        Binding(
            "shift+left", 
            "cursor_parent", 
            "To parent", 
            show=False
        ),
        Binding(
            "shift+right",
            "cursor_parent_next_sibling",
            "To next ancestor",
        ),
        Binding(
            "shift+up",
            "cursor_previous_sibling",
            "To previous sibling",
        ),
        Binding(
            "shift+down",
            "cursor_next_sibling",
            "To next sibling",
        ),
    ]  

    def action_toggle_dotfiles(self) -> None:
        """Toggle the visibility of dotfiles."""
        self.dotfiles = not self.dotfiles
        self.reload()

    def action_cursor_left(self) -> None:
        """Collapse expanded directory or go to parent directory."""
        if self.cursor_node is None:
            return

        current_node = self.cursor_node

        # If the node is expanded and has children, collapse it
        if current_node.is_expanded and current_node.children:
            current_node.collapse()
        else:
            # Otherwise, go to parent
            self.action_cursor_parent()

    def _get_current_path(self) -> Path | None:
        """Get the full path of the currently selected node."""
        if self.cursor_node is None:
            return None

        node = self.cursor_node
        parts = []
        while node:
            # Get the label text (might be formatted as Text object)
            label = node.label
            if hasattr(label, 'plain'):
                # If it's a Text object, use .plain property
                name = label.plain
            else:
                name = str(label)
            # Don't include the root name
            if node.parent is not None:
                parts.append(name)
            node = node.parent
        # Reverse to get correct path order
        parts.reverse()
        
        # Build the full path
        result = self.path
        for part in parts:
            result = result / part
        return result


    def action_edit_file(self) -> None:
        """Open the currently selected file in the configured editor."""
        file_path = self._get_current_path()
        if file_path:
            if file_path.is_file():
                subprocess.Popen([EDITOR, str(file_path)])
                self.app.query_one('#info').content = f"{display_time()} | Opened {file_path.name} in {EDITOR}"
            if file_path.is_dir():
                os.startfile(os.path.realpath(file_path))
                self.app.query_one('#info').content = f"{display_time()} | Opened {file_path} in files"


class TreeDiverApp(App[None]):

    CSS_PATH = "treediver.tcss"
    BINDINGS = [
        Binding("c", "change_root", "Change root"),
        Binding("escape", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        root = os.getcwd()
        #yield Header()
        yield FilteredDirectoryTree(root, id="tree")
        yield PathInput(id="path_input", compact=True)
        yield Label(f"{display_time()} | Started with root {root}", id="info")
        yield Footer(show_command_palette=False)


    def action_edit(self) -> None:
        """ open selected file for editing """
        # subprocess.Popen(["notepad", os.path.realpath(message.path)])
        # self.query_one('#info').content = f"{display_time()} | Opened {message.path.name} for editing"
        self.query_one('#info').content = self.query_one('#tree', FilteredDirectoryTree).cursor_node.label


    @on(DirectoryTree.FileSelected)
    def handle_file_selected(self, message: DirectoryTree.FileSelected) -> None:
        os.startfile(os.path.realpath(message.path))
        self.query_one('#info').content = f"{display_time()} | Ran {message.path.name}"


    def action_change_root(self) -> None:
        """Show the path input for changing the root directory."""
        tree = self.query_one('#tree', FilteredDirectoryTree)
        tree.disabled = True
        path_input = self.query_one('#path_input', Input)
        path_input.placeholder = os.getcwd()
        path_input.value = os.getcwd()
        path_input.display = True
        path_input.focus()
        path_input.cursor_position = len(path_input.value)
        
        
    @on(Input.Submitted)
    def handle_path_submitted(self, event: Input.Submitted) -> None:
        """Handle path input submission."""
        if event.control.id == "path_input":
            new_path = Path(event.value.strip())
            tree = self.query_one('#tree', FilteredDirectoryTree)
            info = self.query_one('#info')
            if new_path and new_path.is_dir():
                tree.path = new_path
                info.content = f"{display_time()} | Changed root to {new_path}"
            else:
                info.content = f"{display_time()} | Invalid path {new_path}"
            
            # Hide the input
            event.control.display = False
            
            # return to tree display
            tree.disabled = False
            tree.focus()


if __name__ == "__main__":
    TreeDiverApp().run()