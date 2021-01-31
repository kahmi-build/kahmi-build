
import argparse
import cProfile, pstats
import logging
import os
import typing as t

from .executors.default import DefaultExecutor, DefaultProgressPrinter
from .model import BuildGraph, Project, Task

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--verbose', action='count', default=0)
parser.add_argument('-f', '--file', default='build.kmi', help='Build script. (default: %(default)s)')
parser.add_argument('targets', nargs='*')
parser.add_argument('--py-profile', action='store_true')


def init_logging(verbosity: int) -> None:
  level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}[min(verbosity, 2)]
  logging.basicConfig(level=level, format='[%(asctime)s - %(levelname)s - %(name)s]: %(message)s')


def main_internal(args: argparse.Namespace) -> None:
  project = Project.from_directory(None, os.path.dirname(args.file))
  project.run_build_script(args.file)

  selected: t.List[Task] = []
  unmatched: t.Set[str] = set(args.targets)
  for task in project.iter_all_tasks():
    for arg in args.targets:
      if (arg.startswith(':') and task.path.endswith(arg)) or (arg == task.name) or arg == task.group:
        selected.append(task)
        unmatched.discard(arg)
        break

  if unmatched:
    parser.error(f'`{next(iter(unmatched))}` did not match any tasks')

  graph = BuildGraph()
  if selected:
    graph.add_tasks(selected)
  else:
    graph.add_project(project)

  executor = DefaultExecutor(DefaultProgressPrinter(always_show_output=args.verbose >= 1))
  executor.execute_graph(graph)


def main(args: t.Optional[t.Sequence[str]] = None) -> None:
  args = parser.parse_args(args)
  init_logging(args.verbose)

  if args.py_profile:
    profiler = cProfile.Profile()
    profiler.runcall(main_internal, args)
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumtime')
    stats.print_stats(.1)
  else:
    main_internal(args)


if __name__ == '__main__':
  main()
