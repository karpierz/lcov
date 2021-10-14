# Copyright (c) 2020-2022, Adam Karpierz
# Licensed under the BSD license
# https://opensource.org/licenses/BSD-3-Clause


def make_config(cfg_name):
    import sys
    from pathlib import Path
    from runpy import run_path
    module = sys.modules[__name__]
    mglobals = module.__dict__
    mglobals.pop("make_config", None)
    cfg_path = Path(module.__file__).parent/cfg_name
    cfg_dict = ({key: val for key, val in run_path(str(cfg_path)).items()
                 if not key.startswith("__")} if cfg_path.is_file() else {})
    mglobals.update(cfg_dict)
    mglobals.pop("__cached__", None)
    module.__all__ = tuple(cfg_dict.keys())


make_config("lcov.cfg")
