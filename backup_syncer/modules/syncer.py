import os
from typing import List, Callable, Any, Dict

from tqdm import tqdm

from backup_syncer.modules import utils
from backup_syncer.modules.backup_syncer_config import BackupSyncerConfig
from backup_syncer.modules.sync_file_types import (
    sync_attribute_create,
    sync_attribute_replace,
)
from backup_syncer.modules.sync_file_types import (
    sync_attribute_outdated,
    sync_attribute_delete,
)
from backup_syncer.modules.utils import check_if_identical


class Syncer:
    CHANGE_MENU = (
        "Changing menu:\n"
        "-> n for new\n"
        "-> d for delete\n"
        "-> r for replace\n"
        "-> o for outdated source\n"
        "-> m for menu\n"
        "-> c for cancel\n"
        "For example, 'r 1' - replace 1."
    )

    length_for_printing = 40

    display_header_seperator: Callable[[Any], None] = lambda self: print("=" * 107)
    display_seperator: Callable[[Any], None] = lambda self: print("~" * 40)

    def __init__(self, backup_syncer_config: BackupSyncerConfig):
        self.directories_to_scan: List[
            Dict[str, str]
        ] = backup_syncer_config.sync_config_dirs

        self.items_to_create: List[sync_attribute_create.SyncAttributeCreate] = []
        # Files that are on the source but not on the destination
        self.items_to_delete: List[sync_attribute_delete.SyncAttributeDelete] = []
        # Files that are on the destination but not on the source, and the source is newer
        self.files_to_replace: List[sync_attribute_replace.SyncAttributeReplace] = []
        # Files that are not updated in the destination, and will be recreated from the source
        self.outdated_files: List[sync_attribute_outdated.SyncAttributeOutdated] = []
        # Files that are newer on the destination than on the source, and won't be replaced
        self.sync_actions_change_options = {
            "n": self.items_to_create,
            "d": self.items_to_delete,
            "r": self.files_to_replace,
            "o": self.outdated_files,
            "m": lambda *args: print(self.CHANGE_MENU),
        }
        self.printing_categories_titles = {
            "Going to be created:": self.items_to_create,
            "Going to be updated:": self.files_to_replace,
            "Going to be deleted:": self.items_to_delete,
            "Outdated source (the destination is newer, won't be replaced):": self.outdated_files,
        }

    def print_sync(self) -> None:
        self.display_header_seperator()
        for title, files_list in self.printing_categories_titles.items():
            if files_list:
                print(title)
                for i, item in enumerate(files_list):
                    print(f"{item}\n")
                self.display_seperator()

    def search_trash_in_backup(self, src_dir_path, backup_dir_path) -> None:
        src_dirs = os.listdir(src_dir_path)
        try:
            backup_dirs = os.listdir(backup_dir_path)
        except NotADirectoryError:
            return

        for item_path in backup_dirs:
            if item_path not in src_dirs:
                item_to_delete = sync_attribute_delete.SyncAttributeDelete(
                    index=len(self.items_to_delete),
                    backup_item_path=os.path.join(backup_dir_path, item_path),
                )
                self.items_to_delete.append(item_to_delete)

    def check_if_sync_actions_change_is_needed(self) -> bool:
        return (
            self.items_to_create
            or self.items_to_delete
            or self.files_to_replace
            or self.outdated_files
        ) and input("Do you want to change something? ([y]/n): ") != "n"

    def make_changes_in_sync_actions(self) -> None:
        change = self.check_if_sync_actions_change_is_needed()
        if change:
            print(self.CHANGE_MENU)
            while change is not False:
                change = input(
                    "Enter n/d/r/o/m/c (number) according to what you want to change: "
                )
                if change == "m":
                    print(self.CHANGE_MENU)
                    continue
                if change == "c":
                    return
                try:
                    action_char, attribute_index = change.split(" ")
                    attribute_index = int(attribute_index)
                    self.sync_actions_change_options[action_char][
                        attribute_index
                    ].change()
                    self.print_sync()
                except Exception:
                    print(f"'{change}' - invalid request.")
                else:
                    change = (
                        input("Do you want to change something else? ([y]/n): ") != "n"
                    )

    def scan_file(
        self, src_file_path: str, src_file_name: str, backup_dir_path: str
    ) -> None:
        backup_dirs = os.listdir(backup_dir_path)

        backup_file_path = os.path.join(backup_dir_path, src_file_name)

        if src_file_name not in backup_dirs:
            item_to_create = sync_attribute_create.SyncAttributeCreate(
                index=len(self.items_to_create),
                original_item_path=src_file_path,
                backup_item_path=os.path.join(backup_dir_path, src_file_name),
            )
            self.items_to_create.append(item_to_create)

        elif not check_if_identical(src_file_path, backup_file_path):
            if os.stat(backup_file_path).st_mtime > os.stat(src_file_path).st_mtime:
                outdated_item = sync_attribute_outdated.SyncAttributeOutdated(
                    index=len(self.outdated_files),
                    original_item_path=src_file_path,
                    backup_item_path=backup_file_path,
                )
                self.outdated_files.append(outdated_item)
            else:
                item_to_replace = sync_attribute_replace.SyncAttributeReplace(
                    index=len(self.files_to_replace),
                    original_item_path=src_file_path,
                    backup_item_path=backup_file_path,
                )
                self.files_to_replace.append(item_to_replace)

    def scan_directory(
        self, src_dir_path: str, backup_dir_path: str, progress_bar: tqdm
    ) -> None:
        self.search_trash_in_backup(src_dir_path, backup_dir_path)

        backup_directories = os.listdir(backup_dir_path)
        for src_dir in os.listdir(src_dir_path):
            src_subdir_path = os.path.join(src_dir_path, src_dir)
            backup_subdir_path = os.path.join(backup_dir_path, src_dir)

            if not os.path.isdir(src_subdir_path):
                self.scan_file(src_subdir_path, src_dir, backup_dir_path)
                progress_bar.update(1)

            elif src_dir in backup_directories:
                if os.path.isdir(backup_subdir_path):
                    self.scan_directory(
                        src_subdir_path, backup_subdir_path, progress_bar=progress_bar
                    )
                else:
                    item = sync_attribute_delete.SyncAttributeDelete(
                        index=len(self.items_to_delete),
                        backup_item_path=backup_subdir_path
                    )
                    self.items_to_delete.append(item)
                    item = sync_attribute_create.SyncAttributeCreate(
                        index=len(self.items_to_create),
                        original_item_path=src_subdir_path,
                        backup_item_path=backup_subdir_path
                    )
                    self.items_to_create.append(item)

            else:
                to_create_item = sync_attribute_create.SyncAttributeCreate(
                    index=len(self.items_to_create),
                    original_item_path=src_subdir_path,
                    backup_item_path=backup_subdir_path,
                )
                self.items_to_create.append(to_create_item)
                progress_bar.update(utils.get_files_count(src_subdir_path))

    def perform_sync(self) -> None:
        for item in (
            self.items_to_delete
            + self.files_to_replace
            + self.items_to_create
            + self.outdated_files
        ):
            if not item.is_canceled:
                print(item)
                item.action()

    def scan_directories(self) -> None:
        for line in self.directories_to_scan:
            with tqdm(
                total=utils.get_files_count(line["src"]),
                unit="F",
                unit_scale=True,
                desc=f"Scanning {line['src']}",
                miniters=0.1,
            ) as pbar:
                self.scan_directory(
                    src_dir_path=line["src"],
                    backup_dir_path=line["backup"],
                    progress_bar=pbar,
                )
