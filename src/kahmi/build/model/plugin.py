
import importlib
import typing as t

if t.TYPE_CHECKING:
  from .project import Project


def apply_plugin(plugin_name: str, project: 'Project') -> None:
  module_name = 'kahmi.build.lib.' + plugin_name
  try:
    module = importlib.import_module(module_name)
  except ImportError as exc:
    if module_name not in exc.msg.replace(exc.path, ''):
      raise
    module = importlib.import_module(plugin_name)
  module.apply(project)  # type: ignore
