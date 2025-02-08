import abc

from backup_syncer.modules.utils import get_item_type


class SyncAttribute(abc.ABC):
    length_for_printing = 40

    def __init__(self, index: int, original_item_path: str, backup_item_path: str):
        self.index = index
        self.source_file_path = original_item_path
        self.backup_file_path = backup_item_path
        if self.source_file_path:
            self.item_type = get_item_type(self.source_file_path)
        else:
            self.item_type = get_item_type(self.backup_file_path)
        self.is_canceled = False

    def remove(self):
        self.source_file_path = "<Canceled>"
        self.backup_file_path = "<Canceled>"
        self.is_canceled = True

    @abc.abstractmethod
    def change(self):
        ...

    @abc.abstractmethod
    def action(self):
        ...

    @abc.abstractmethod
    def __present__(self):
        ...

    def __eq__(self, other):
        if not issubclass(type(other), SyncAttribute) and not isinstance(
            other, SyncAttribute
        ):
            return False
        return (
            self.item_type == other.item_type
            and self.is_canceled == other.is_canceled
            and self.source_file_path == other.source_file_path
            and self.backup_file_path == other.backup_file_path
        )

    def __str__(self):
        if self.is_canceled:
            return f"{self.index} - <Canceled>"
        else:
            return self.__present__()
