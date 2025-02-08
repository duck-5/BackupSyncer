import os
from typing import List, Dict
from pathlib import Path


class BackupSyncerConfig:
    NOTE_MARKER = "#"
    SRC_AND_BACKUP_SEPARATOR = " | "
    DEFAULT_CONFIG_FILE_PATH = (
        Path(os.getenv("APPDATA")) / "BackupSyncer" / "backup-syncer.config"
    )
    CONFIG_TEMPLATE = r"""# This is a config file template.
# setup attribute should be in the format of:
# <path_to_source_directory> | <path_to_backup_directory>
# Attributes starting with "#" will be ignored!

# Example:
a\path\to\an\src\dir | a\path\to\a\backup\dir
a\new\path\to\an\src\dir | a\new\path\to\a\backup\dir

# You can add as many pairs as you want.
"""

    def __init__(self, config_fp: Path = DEFAULT_CONFIG_FILE_PATH):
        print(f"Using config file: {config_fp}")
        self._config_fp: Path = config_fp
        self.sync_config_dirs: List[Dict[str, str]] = []
        self._update_sync_config_dirs()

    def _create_sync_config_file_if_gone(self) -> None:
        if self._config_fp.is_dir():
            raise FileNotFoundError(
                f"Config file not found and cannot be created: {self._config_fp} is a directory"
            )

        if not self._config_fp.exists():
            os.makedirs(self._config_fp.parent)
            with open(self._config_fp, "w") as config_file:
                config_file.write(self.CONFIG_TEMPLATE)
                print(f"Config file not found, created at {self._config_fp}")

    def _update_sync_config_dirs(self) -> None:
        """
        Update the sync_config_dirs attribute by the config file and update the config file, until the user is happy.
        :return: None
        """
        if not os.path.exists(self._config_fp):
            self._update_config_file()

        self.sync_config_dirs = self._get_sync_config_dirs_from_configuration()
        self.display()

        while input("Fine? ([y]/n): ") == "n":
            self._update_config_file()
            self.sync_config_dirs = self._get_sync_config_dirs_from_configuration()
            self.display()

        self._create_missing_backup_directories()

    def _get_sync_config_dirs_from_configuration(self) -> List[Dict[str, str]]:
        """
        Get the source and backup directories from the config file.
        :return: A list of source and backup directories.
        """
        configuration = []
        with open(self._config_fp, "r", encoding="UTF-8") as config_file:
            dir_paths = config_file.read().split("\n")
            for line in dir_paths:
                if self._validate_config_file_attribute(line):
                    line = line.split(self.SRC_AND_BACKUP_SEPARATOR)
                    configuration.append({"src": line[0], "backup": line[1]})
        return configuration

    def _update_config_file(self) -> None:
        """
        Create the config file if it doesn't exist and open it with notepad for editing.
        :return: None
        """
        self._create_sync_config_file_if_gone()
        os.system(f"notepad {self._config_fp}")

    def _create_missing_backup_directories(self):
        """
        Create backup directories that doesn't exist.
        :return:
        """
        for sync_config_attribute in self.sync_config_dirs:
            backup_dir_path = sync_config_attribute["backup"]
            if not os.path.exists(backup_dir_path):
                print(f"{backup_dir_path} doesn't exists, creating...")
                os.makedirs(backup_dir_path)

    def _validate_config_file_attribute(self, attribute: str) -> bool:
        """
        Validates a config attribute.
        :param attribute: A config-file attribute.
        :return: If the attribute is valid.
        """
        return self._config_file_attribute_string_validation(
            attribute
        ) and self._config_file_attribute_src_and_backup_validation(attribute)

    def _config_file_attribute_string_validation(self, attribute: str):
        """
        Validates a config-file attribute -> If this attribute is a source-backup format attribute.
        :param attribute: A line from the config file.
        :return: If the attribute's format is valid.
        """
        if not attribute or attribute[0] == self.NOTE_MARKER:
            return False
        if self.SRC_AND_BACKUP_SEPARATOR not in attribute:
            print(
                f"Invalid: '{attribute}' doesn't contain {self.SRC_AND_BACKUP_SEPARATOR}, skipping..."
            )
            return False
        if attribute.count(self.SRC_AND_BACKUP_SEPARATOR) != 1:
            print(
                f"Invalid: '{attribute}' can't contain {self.SRC_AND_BACKUP_SEPARATOR} more than once, skipping..."
            )
            return False
        return True

    def _config_file_attribute_src_and_backup_validation(self, attribute: str) -> bool:
        """
        Validates the source and backup directories of an attribute.
        :param attribute: A config-file attribute.
        :return: If the attribute's directories are valid (exists, etc.)
        """
        src_dir_path, backup_dir_path = attribute.split(self.SRC_AND_BACKUP_SEPARATOR)

        if not os.path.exists(src_dir_path):
            print(f"{src_dir_path} doesn't exist, skipping...")
        elif not os.path.isdir(src_dir_path):
            print(f"{src_dir_path} exists but not a directory, skipping...")
        elif os.path.exists(backup_dir_path) and not os.path.isdir(backup_dir_path):
            print(f"{backup_dir_path} exists but not a directory, skipping...")
        else:
            return True
        return False

    def display(self) -> None:
        print(f"{'~' * 40}\nSetup is:\n{self}")

    def __str__(self) -> str:
        string_repr = ""
        for sync_config_attribute in self.sync_config_dirs:
            string_repr += (
                f"src: ~~~~~~~~~ {sync_config_attribute['src']} "
                f"backup : ~~~~~~~~~ {sync_config_attribute['backup']}"
                f"\n"
            )
        return string_repr
