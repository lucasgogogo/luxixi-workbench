#!/bin/sh
set -eu
task_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
task_python="$task_dir/.venv/bin/python"
if [ ! -x "$task_python" ]; then
  echo 'Missing isolated Python environment; Skill installer is planned for T004.' >&2
  exit 1
fi
cd "$task_dir"
exec "$task_python" -X utf8 -B -m luxixi_workbench "$@"
