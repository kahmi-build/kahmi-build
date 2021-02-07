
import argparse
import cProfile, pstats
import logging
import os
import sys
import typing as t

from .executors.default import DefaultExecutor, DefaultProgressPrinter
from .model import BuildGraph, Environment, Project, SqliteStateTracker, Task

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--verbose', action='count', default=0)
parser.add_argument('-s', '--no-capture', action='store_true')
parser.add_argument('-f', '--file', default='build.kmi', help='Build script. (default: %(default)s)')
parser.add_argument('-j', '--jobs', type=int, help='Max number of parallel tasks to execute.')
parser.add_argument('targets', nargs='*')
parser.add_argument('--py-profile', action='store_true')


def init_logging(verbosity: int) -> None:
  level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}[min(verbosity, 2)]
  logging.basicConfig(level=level, format='[%(asctime)s - %(levelname)s - %(name)s]: %(message)s')


def main_internal(args: argparse.Namespace) -> None:
  env = Environment()
  env.root_project = Project.from_directory(env, None, os.path.dirname(args.file))
  env.state_tracker = SqliteStateTracker(os.path.join(
    env.root_project.build_directory, '.kahmi', 'build_state.db'))
  env.root_project.run_build_script(args.file)
  env.graph.add_project(env.root_project)

  if args.targets:
    for task in env.root_project.resolve_tasks(args.targets):
      env.graph.select(task)
  else:
    env.graph.select_defaults()

  printer = DefaultProgressPrinter(always_show_output=args.no_capture or args.verbose >= 1)
  executor = DefaultExecutor(printer, args.jobs)
  executor.execute_graph(env.graph)


def main(argv: t.Optional[t.Sequence[str]] = None) -> None:
  args = parser.parse_args(argv)
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
