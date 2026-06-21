import argparse
import os
import subprocess
import time
import shutil
import sys

from pathlib import Path
from typing import Iterable

from textual import on
from textual.binding import Binding
from textual.app import App, ComposeResult
from textual.widgets import DirectoryTree, Footer, Label, Input

version = "0.0.1"


def display_time() -> str:
    return time.strftime('%H:%M:%S')


def parse() -> tuple[Path, str | None]:
    """Parse CLI arguments and return (root, editor). Exits on bad input."""
    parser = argparse.ArgumentParser(
        prog='treediver',
        description='a tree-based file explorer'
    )
    parser.add_argument(
        '-r', '--root',
        nargs=1,
        type=Path,
        help="the root for the program. defaults to current working directory.",
    )
    parser.add_argument(
        '-e', '--editor',
        nargs=1,
        type=str,
        help="the editor to use. uses your $EDITOR environment variable by default.",
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {version}'
    )

    args = parser.parse_args()

    root = Path(os.getcwd())
    if args.root:
        root = Path(os.path.realpath(args.root[0]))
        if not root.exists():
            sys.exit(f"error: root path does not exist: {root}")
        if not root.is_dir():
            sys.exit(f"error: root path is not a directory: {root}")

    editor = os.environ.get('EDITOR', None)
    if args.editor:
        editor = args.editor[0]
        if not shutil.which(editor):
            sys.exit(f"error: cannot find editor: {editor}")

    return root, editor


class PathInput(Input):
    """Path entry widget with escape-to-cancel support."""
    BINDINGS = [
        Binding("enter", "submit", "Submit"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def action_cancel(self) -> None:
        tree = self.app.query_one('#tree', FilteredDirectoryTree)
        self.display = False
        tree.disabled = False
        tree.focus()


class FilteredDirectoryTree(DirectoryTree):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.dotfiles = False

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return paths if self.dotfiles else [
            path for path in paths if not path.name.startswith(".")
        ]

    BINDINGS = [
        Binding("a", "toggle_dotfiles", "Toggle dotfiles"),
        Binding("e", "edit_file", "Edit file"),
        Binding("alt+c", "make_root", "Select as root"),
        Binding("alt+up", "root_up", "Move root up"),
        Binding("left", "cursor_left", "Collapse/To parent", show=False),
        Binding("right", "select_cursor", "Run", show=False),
        Binding("shift+left", "cursor_parent", "To parent", show=False),
        Binding("shift+right", "cursor_parent_next_sibling", "To next ancestor", show=False),
        Binding("shift+up", "cursor_previous_sibling", "To previous sibling", show=False),
        Binding("shift+down", "cursor_next_sibling", "To next sibling", show=False),
    ]

    def action_toggle_dotfiles(self) -> None:
        self.dotfiles = not self.dotfiles
        self.reload()

    def action_cursor_left(self) -> None:
        if self.cursor_node is None:
            return
        node = self.cursor_node
        if node.is_expanded and node.children:
            node.collapse()
        else:
            self.action_cursor_parent()

    def _current_path(self) -> Path | None:
        """return the Path for the currently highlighted node."""
        if self.cursor_node is None:
            return None
        
        node_data = self.cursor_node.data
        if node_data is not None and hasattr(node_data, 'path'):
            return node_data.path
        return None

    def action_edit_file(self) -> None:
        """open the selected node in editor (files) or file manager (dirs)."""
        path = self._current_path()
        info = self.app.query_one('#info')
        editor = self.app._editor

        if path is None:
            return

        if path.is_file():
            if editor is None:
                info.content = f"{display_time()} | No editor configured (set $EDITOR or use -e)"
                return
            subprocess.Popen([str(editor), str(path)])
            info.content = f"{display_time()} | Opened {path.name} in {editor}"
        elif path.is_dir():
            os.startfile(os.path.realpath(path))
            info.content = f"{display_time()} | Opened {path} in files"

    def action_make_root(self) -> None:
        path = self._current_path()
        info = self.app.query_one('#info')
        if path and path.is_dir():
            self.path = path
            info.content = f"{display_time()} | Changed root to {path}"
        else:
            info.content = f"{display_time()} | Cannot set a file as root"

    def action_root_up(self) -> None:
        parent = self.path.parent
        info = self.app.query_one('#info')
        if parent == self.path:
            info.content = f"{display_time()} | Already at filesystem root"
            return
        self.path = parent
        info.content = f"{display_time()} | Changed root to {parent}"


class TreeDiverApp(App[None]):

    CSS_PATH = Path(__file__).parent / "treediver.tcss"
    BINDINGS = [
        Binding("c", "change_root", "Change root"),
        Binding("escape", "quit", "Quit"),
    ]

    def __init__(self, root: Path, editor: str | None) -> None:
        super().__init__()
        self._root = root
        self._editor = editor

    def compose(self) -> ComposeResult:
        yield FilteredDirectoryTree(self._root, id="tree")
        yield PathInput(id="path_input", compact=True)
        yield Label(f"{display_time()} | Started with root {self._root}", id="info")
        yield Footer(show_command_palette=False)

    @on(DirectoryTree.FileSelected)
    def handle_file_selected(self, message: DirectoryTree.FileSelected) -> None:
        os.startfile(os.path.realpath(message.path))
        self.query_one('#info').content = f"{display_time()} | Ran {message.path.name}"

    def action_change_root(self) -> None:
        """bring up new root path entry"""
        tree = self.query_one('#tree', FilteredDirectoryTree)
        tree.disabled = True
        path_input = self.query_one('#path_input', PathInput)
        path_input.value = str(tree.path)
        path_input.placeholder = str(tree.path)
        path_input.display = True
        path_input.focus()
        path_input.cursor_position = len(path_input.value)

    @on(Input.Submitted)
    def handle_path_submitted(self, event: Input.Submitted) -> None:
        if event.control.id != "path_input":
            return
        new_path = Path(event.value.strip())
        tree = self.query_one('#tree', FilteredDirectoryTree)
        info = self.query_one('#info')
        if new_path.is_dir():
            tree.path = new_path
            info.content = f"{display_time()} | Changed root to {new_path}"
        else:
            info.content = f"{display_time()} | Invalid path: {new_path}"
        event.control.display = False
        tree.disabled = False
        tree.focus()


def main():
    root, editor = parse()
    TreeDiverApp(root, editor).run()

if __name__ == "__main__":
    main()
