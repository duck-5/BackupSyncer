import os
import shutil

from backup_syncer.modules.utils import copy_dir_with_pbar, copy_file_with_pbar
from backup_syncer.modules.sync_file_types.sync_attribute import SyncAttribute


class SyncAttributeCreate(SyncAttribute):
    def change(self):
        if self.is_canceled:
            print("Already canceled...")
            return
        self.remove()

    def action(self):
        if self.is_canceled:
            return

        if self._is_item_invalid_file():
            self.is_canceled = True
            print(f"Item {self.index} is canceled (invalid file)")
            return

        if self.item_type == "directory":
            os.mkdir(self.backup_file_path)
            copy_dir_with_pbar(
                src_dp=self.source_file_path, backup_dp=self.backup_file_path
            )

        else:
            copy_file_with_pbar(
                src_fp=self.source_file_path, backup_fp=self.backup_file_path
            )

    def _is_item_invalid_file(self) -> bool:
        if self.item_type == "file":
            try:
                os.path.getsize(self.source_file_path)
            except OSError:
                return True
        return False

    def __present__(self):
        return (
            f"{self.index} {f'New ({self.item_type}) ':-<{self.length_for_printing}} {self.backup_file_path}\n"
            f"{self.index} {f'From ({self.item_type}) ':-<{self.length_for_printing}} {self.source_file_path}"
        )
