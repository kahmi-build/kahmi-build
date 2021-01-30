
import argparse
import os

from .executors.default import DefaultExecutor
from .model import BuildGraph, Project, Task

parser = argparse.ArgumentParser()
parser.add_argument('-f', '--file', default='build.kmi', help='Build script. (default: %(default)s)')
parser.add_argument('targets', nargs='*')


def main() -> None:
  args = parser.parse_args()

  project = Project.from_directory(None, os.path.dirname(args.file))
  project.run_build_script(args.file)

  selected: t.List[Task] = []
  for task in project.iter_all_tasks():
    for arg in args.targets:
      if (arg.startswith(':') and task.path.endswith(arg)) or (arg == task.name) or arg == task.group:
        selected.append(task)
        break

  graph = BuildGraph()
  if selected:
    graph.add_tasks(selected)
  else:
    graph.add_project(project)

  executor = DefaultExecutor()
  executor.execute_graph(graph)


if __name__ == '__main__':
  main()
