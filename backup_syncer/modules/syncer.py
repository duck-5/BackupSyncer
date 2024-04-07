from multiprocessing import Process
import multiprocessing
import os
import time
from typing import List, Callable, Any, Dict, Tuple

from tqdm import tqdm
from threading import Thread
from backup_syncer.modules import utils
from backup_syncer.modules.backup_syncer_config import BackupSyncerConfig

from backup_syncer.modules.sync_file_types import SyncAttribute, SyncAttributeDelete, SyncAttributeReplace, SyncAttributeOutdated, SyncAttributeCreate
from backup_syncer.modules.utils import check_if_identical, remove_duplicates


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
        self.items_to_scan: List[Tuple[str, str, str]] = []

        self.items_to_create: List[SyncAttributeCreate] = []
        # Files that are on the source but not on the destination
        self.items_to_delete: List[SyncAttributeDelete] = []
        # Files that are on the destination but not on the source, and the source is newer
        self.files_to_replace: List[SyncAttributeReplace] = []
        # Files that are not updated in the destination, and will be recreated from the source
        self.outdated_files: List[SyncAttributeOutdated] = []
        # Files that are newer on the destination than on the source, and won't be replaced

        self.type2list: Dict[Any, List] = {
            SyncAttributeCreate: self.items_to_create,
            SyncAttributeDelete: self.items_to_delete,
            SyncAttributeReplace: self.files_to_replace,
            SyncAttributeOutdated: self.outdated_files
        }

        self.sync_actions_change_options = {
            "n": self.items_to_create,
            "d": self.items_to_delete,
            "r": self.files_to_replace,
            "o": self.outdated_files,
            "m": lambda *args: print(self.CHANGE_MENU),
        }
        self.create_categories_titles = lambda: {
            "Going to be created:": self.items_to_create,
            "Going to be updated:": self.files_to_replace,
            "Going to be deleted:": self.items_to_delete,
            "Outdated source (the destination is newer, won't be replaced):": self.outdated_files,
        }
        self.threads: List[Thread] = []

    def print_sync(self) -> None:
        self.display_header_seperator()
        for title, files_list in self.create_categories_titles().items():
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
                item_to_delete = SyncAttributeDelete(
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

    def scan_files(self, max_number_of_processes: int, pbar, min_files_per_process: int = 500):

        number_of_processes = min(max_number_of_processes, len(self.items_to_scan) // min_files_per_process)
        number_of_files_per_process = len(self.items_to_scan) // number_of_processes + 1
        progress_bar_queue = multiprocessing.Queue()
        items_queue = multiprocessing.Queue()
        processes = []
        pbar.write(f"\nRunning with {number_of_processes} processes, {number_of_files_per_process} files per process")

        for i in range(0, len(self.items_to_scan), number_of_files_per_process):
            p = Process(target=scan_files, args=(self.items_to_scan[i:i + number_of_files_per_process], items_queue, progress_bar_queue))
            processes.append(p)
            p.start()

        while any([p.is_alive() for p in processes]):
            while not progress_bar_queue.empty():
                pbar.update(progress_bar_queue.get())
            while not items_queue.empty():
                item = items_queue.get()
                self.put_item_in_list(item)

    def scan_directory(
        self, src_dir_path: str, backup_dir_path: str, progress_bar: tqdm
    ) -> None:
        for t in self.threads:
            if not t.is_alive():
                self.threads.remove(t)

        self.search_trash_in_backup(src_dir_path, backup_dir_path)

        backup_directories = os.listdir(backup_dir_path)
        for src_dir in os.listdir(src_dir_path):
            src_subdir_path = os.path.join(src_dir_path, src_dir)
            backup_subdir_path = os.path.join(backup_dir_path, src_dir)

            if not os.path.isdir(src_subdir_path):
                self.items_to_scan.append((src_subdir_path, src_dir, backup_dir_path))
                progress_bar.update(1)

            elif src_dir in backup_directories:
                if os.path.isdir(backup_subdir_path):
                    self.scan_directory(
                        src_subdir_path, backup_subdir_path, progress_bar=progress_bar
                    )
                else:
                    item = SyncAttributeDelete(
                        index=len(self.items_to_delete),
                        backup_item_path=backup_subdir_path
                    )
                    self.items_to_delete.append(item)
                    item = SyncAttributeCreate(
                        index=len(self.items_to_create),
                        original_item_path=src_subdir_path,
                        backup_item_path=backup_subdir_path
                    )
                    self.items_to_create.append(item)

            else:
                to_create_item = SyncAttributeCreate(
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

            with tqdm(
                    total=len(self.items_to_scan),
                    unit="F",
                    unit_scale=True,
                    desc=f"Scanning {len(self.items_to_scan)}",
                    miniters=0.1,
            ) as pbar:
                self.scan_files(5, pbar=pbar)

        self.items_to_create = remove_duplicates(self.items_to_create)
        self.items_to_delete = remove_duplicates(self.items_to_delete)
        self.files_to_replace = remove_duplicates(self.files_to_replace)
        self.outdated_files = remove_duplicates(self.outdated_files)

    def put_item_in_list(self, item: SyncAttribute):
        lst = self.type2list[type(item)]
        item.index = len(lst)
        lst.append(item)


def scan_file(
        src_file_path: str, src_file_name: str, backup_dir_path: str
) -> SyncAttribute:
    backup_dirs = os.listdir(backup_dir_path)

    backup_file_path = os.path.join(backup_dir_path, src_file_name)

    if src_file_name not in backup_dirs:
        return SyncAttributeCreate(
            index=1,
            original_item_path=src_file_path,
            backup_item_path=os.path.join(backup_dir_path, src_file_name),
        )

    elif not check_if_identical(src_file_path, backup_file_path):
        if os.stat(backup_file_path).st_mtime > os.stat(src_file_path).st_mtime:
            return SyncAttributeOutdated(
                index=1,
                original_item_path=src_file_path,
                backup_item_path=backup_file_path,
            )
        else:
            return SyncAttributeReplace(
                index=1,
                original_item_path=src_file_path,
                backup_item_path=backup_file_path,
            )


def scan_files(items_to_scan, items_queue: multiprocessing.Queue, progress_bar_queue: multiprocessing.Queue):
    for file_data in items_to_scan:
        item = scan_file(*file_data)
        progress_bar_queue.put(1)
        if item:
            items_queue.put(item)
