from backup_syncer.modules.backup_syncer_config import BackupSyncerConfig
from backup_syncer.modules.syncer import Syncer


def main():
    backup_syncer_config = BackupSyncerConfig()
    syncer = Syncer(backup_syncer_config)
    syncer.scan_directories()
    syncer.print_sync()
    syncer.make_changes_in_sync_actions()
    syncer.perform_sync()
    input("Sync was successful! Press enter to exit")


if __name__ == "__main__":
    main()
