
import importlib
import typing as t

if t.TYPE_CHECKING:
  from .project import Project


def apply_plugin(plugin_name: str, project: 'Project') -> None:
  module_name = 'kahmi.build.lib.' + plugin_name
  module = importlib.import_module(module_name)
  module.apply(project)
