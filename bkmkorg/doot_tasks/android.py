#!/usr/bin/env python3
"""

"""
##-- imports
from __future__ import annotations

import shutil
import abc
import logging as logmod
import sys
import pathlib as pl
from copy import deepcopy
from dataclasses import InitVar, dataclass, field
from re import Pattern
from typing import (TYPE_CHECKING, Any, Callable, ClassVar, Final, Generic,
                    Iterable, Iterator, Mapping, Match, MutableMapping,
                    Protocol, Sequence, Tuple, TypeAlias, TypeGuard, TypeVar,
                    cast, final, overload, runtime_checkable)
from uuid import UUID, uuid1
from weakref import ref

if TYPE_CHECKING:
    # tc only imports
    pass
##-- end imports

##-- logging
logging = logmod.getLogger(__name__)
# If CLI:
# logging = logmod.root
# logging.setLevel(logmod.NOTSET)
##-- end logging

import doot
from doot.tasker import DootTasker
from doot.task_mixins import ActionsMixin, BatchMixin
from doot import globber
from bkmkorg.apis import android

android_base : Final = doot.config.on_fail("/storage/6331-3162", str).tools.doot.android.base(wrapper=pl.Path)
timeout      : Final = doot.config.on_fail(5, int).tools.doot.android.timeout()
port         : Final = doot.config.on_fail(37769, int).tools.doot.android.port()
wait_time    : Final = doot.config.on_fail(10, int).tools.doot.android.wait()

NICE         : Final = ["nice", "-n", "10"]

class ADBUpload(android.ADBMixin, globber.DirGlobMixin, globber.DootEagerGlobber, ActionsMixin):
    """
    Push files from local to device
    """

    def __init__(self, name="android::upload", locs=None, roots=None, rec=True):
        super().__init__(name, locs, roots or [locs.local_push], rec=rec)
        self.device_root = None
        self.local_root  = None
        self.report      = list()
        self.count = 0

    def filter(self, fpath):
        if fpath.parent in self.roots:
            return self.control.keep
        return self.control.discard

    def set_params(self):
        return [
            {"name": "id", "long": "id", "type": str, "default": None},
            {"name": "remote", "long": "remote", "type": str, "default": "."},
        ]

    def task_detail(self, task):
        self.device_root = android_base / self.args['remote']
        self.local_root  = self.locs.local_push
        print(f"Set Device Root to: {self.device_root}")
        task.update({
            "actions" : [ self.write_report ],
        })
        return task

    def subtask_detail(self, task, fpath):
        task.update({
            "actions" : [ self.cmd(self.args_adb_push_dir, fpath, save="result"),
                          (self.add_to_log, [fpath]),
                         ],
        })
        return task

    def add_to_log(self, fpath, task):
        entry = f"{fpath}: {task.values['result']}"
        self.report.append(entry)

    def write_report(self):
        print("Completed")
        report = []
        report.append("--------------------")
        report.append("Pushed: ")
        report += [str(x) for x in self.report]

        (self.locs.build / "adb_push.report").write_text("\n".join(report))

class ADBDownload(android.ADBMixin, DootTasker, ActionsMixin, BatchMixin):
    """
    pull files from device to local
    """

    def __init__(self, name="android::download", locs=None):
        super().__init__(name, locs)
        self.report      = {}
        self.device_root = None
        self.local_root  = None
        assert(locs.local_pull)

    def set_params(self):
        return [
            {"name": "id", "long": "id", "type": str, "default": None},
            {"name": "remote", "long": "remote", "type": str, "default": "."},
            {"name" : "local", "long": "local", "type": str, "default": str(self.locs.local_pull)},
        ]

    def task_detail(self, task):
        self.device_root = android_base / self.args['remote']
        self.local_root  = pl.Path(self.args['local'])
        task.update({
            "actions" : [ self.cmd(self.args_adb_query, ftype="f", save="immediate_files"),
                          self.cmd(self.args_adb_query,            save="remote_subdirs"),
                          (self.batch_query_subdirs, [self._subbatch_query] ), # -> remote_files
                          self.calc_pull_targets, # -> pull_targets
                          self.pull_files, # -> downloaded, failed
                          self.write_report,
                         ],
            "verbosity" : 2,
        })
        return task

    def _subbatch_query(self, data):
        """
        Run a single query directory query
        """
        print(f"Subdir Batch: {data}", file=sys.stderr)
        query = self.cmd(self.args_adb_query(data[0], depth=-1, ftype="f"))
        query.execute()
        query_result = {x.strip() for x in query.out.split("\n")}
        return query_result

    def calc_pull_targets(self, task):
        device_set = { pl.Path(x.strip()).relative_to(self.device_root) for x in task.values['remote_files']}
        local_set  = { x.relative_to(self.local_root) for x in self.local_root.rglob("*") }

        pull_set = device_set - local_set
        print(f"Pull Set: {len(pull_set)}")
        return { "pull_targets" : [str(x) for x in pull_set] }

    def write_report(self, task):
        report = []
        report.append("--------------------")
        report.append("Pull Targets From Device: ")
        report += task.values['pull_targets']

        report.append("--------------------")
        report.append("Downloaded: ")
        report += task.values['downloaded']

        report.append("--------------------")
        report.append("Failed: ")
        report += task.values['failed']

        (self.locs.build / "adb_pull.report").write_text("\n".join(report))
