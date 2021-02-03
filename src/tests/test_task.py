
from pathlib import Path

from kahmi.build.model.task import Task
from kahmi.build.model.project import Project
from kahmi.build.model.property import Property


def test_task_dependencies_through_properties():
  project = Project(None, 'test', Path.cwd())

  class ProducerTask(Task):
    output_file: Property[str] = Property(None, Task.Output)
    output_file_without_marker: Property[str]

  class ConsumerTask(Task):
    input_file: Property[str] = Property(None, Task.InputFile)

  task1 = project.task('task1', ProducerTask)
  task2 = project.task('task2', ConsumerTask)
  task2.input_file.set(task1.output_file)

  assert task2.compute_all_dependencies() == {task1}

  task3 = project.task('task3', ProducerTask)
  task4 = project.task('task4', ConsumerTask)
  task4.input_file.set(task3.output_file_without_marker)

  assert task4.compute_all_dependencies() == set()
