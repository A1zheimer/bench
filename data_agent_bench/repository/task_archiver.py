import json
import logging
import pathlib
import shutil
import base64
from typing import List, Optional

logger = logging.getLogger(__name__)

class TaskArchiver:
    """
    Manages the lifecycle of generated tasks.
    Compresses completed tasks from tasks/ directory into a single JSONL archive,
    and allows restoring them back for regression testing.
    """
    
    def __init__(self, tasks_dir: str = "./tasks", runs_dir: str = "./bench_runs", archive_file: str = "./archives/archived_tasks.jsonl"):
        self.tasks_dir = pathlib.Path(tasks_dir)
        self.runs_dir = pathlib.Path(runs_dir)
        self.archive_file = pathlib.Path(archive_file)
        self.archive_file.parent.mkdir(parents=True, exist_ok=True)

    def archive_executed_tasks(self) -> int:
        """
        Scans bench_runs/ for executed tasks, archives their source task folder,
        and deletes the original task folder to keep the tasks/ directory clean.
        Returns the number of tasks archived.
        """
        if not self.runs_dir.exists():
            logger.info("No bench_runs directory found. Nothing to archive.")
            return 0

        executed_task_ids = set()
        for run_path in self.runs_dir.iterdir():
            if run_path.is_dir() and run_path.name.startswith("DS_TASK_"):
                executed_task_ids.add(run_path.name)

        archived_count = 0
        for task_id in executed_task_ids:
            task_path = self.tasks_dir / task_id
            if task_path.exists() and task_path.is_dir():
                try:
                    self._archive_single_task(task_path)
                    shutil.rmtree(task_path)
                    archived_count += 1
                    logger.info(f"Archived and cleaned up task: {task_id}")
                except Exception as e:
                    logger.error(f"Failed to archive task {task_id}: {e}")

        return archived_count

    def _archive_single_task(self, task_path: pathlib.Path):
        task_data = {
            "instance_id": task_path.name,
            "files": {}
        }

        # Recursively read all files in the task directory
        for file_path in task_path.rglob('*'):
            if file_path.is_file():
                rel_path = file_path.relative_to(task_path).as_posix()
                try:
                    # Try to read as utf-8 text first (for json, csv, py)
                    content = file_path.read_text(encoding='utf-8')
                    task_data["files"][rel_path] = {"type": "text", "content": content}
                except UnicodeDecodeError:
                    # Fallback to base64 for binary files if any
                    content = base64.b64encode(file_path.read_bytes()).decode('ascii')
                    task_data["files"][rel_path] = {"type": "base64", "content": content}

        # Append to jsonl
        with open(self.archive_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(task_data) + "\n")

    def restore_task(self, task_id: str) -> bool:
        """
        Restores a specific task from the archive back to the tasks/ directory.
        Returns True if successful.
        """
        if not self.archive_file.exists():
            logger.error("Archive file not found.")
            return False

        restored = False
        with open(self.archive_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    task_data = json.loads(line)
                    if task_data.get("instance_id") == task_id:
                        self._extract_task(task_data)
                        restored = True
                        logger.info(f"Restored task {task_id} from archive.")
                        break
                except json.JSONDecodeError:
                    continue

        if not restored:
            logger.warning(f"Task {task_id} not found in archive.")
        
        return restored

    def _extract_task(self, task_data: dict):
        task_path = self.tasks_dir / task_data["instance_id"]
        task_path.mkdir(parents=True, exist_ok=True)

        for rel_path, file_info in task_data.get("files", {}).items():
            dest_path = task_path / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            if file_info["type"] == "text":
                dest_path.write_text(file_info["content"], encoding="utf-8")
            elif file_info["type"] == "base64":
                dest_path.write_bytes(base64.b64decode(file_info["content"]))