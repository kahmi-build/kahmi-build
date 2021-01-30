
import argparse
import os

from .model import BuildGraph, Project

parser = argparse.ArgumentParser()
parser.add_argument('-f', '--file', default='build.kmi', help='Build script. (default: %(default)s)')


def main() -> None:
  args = parser.parse_args()
  project = Project.from_directory(None, os.path.dirname(args.file))
  project.run_build_script(args.file)
  graph = BuildGraph()
  graph.add_project(project)
  for task in graph.topological_order():
    task.execute()
    task.reraise_error()


if __name__ == '__main__':
  main()
