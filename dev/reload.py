"""Reload the add-in inside a running Fusion session (development helper).

Fusion has no API to restart an add-in, so this stops it, drops its modules and
imports it again the way Fusion does. Run it inside Fusion, for example from a dev
bridge: exec(open(".../dev/reload.py").read(), {"ADDIN_DIR": ".../CounterboreBridging"})
"""

import importlib.util
import os
import sys


def reload_addin(addin_dir):
    main_file = os.path.realpath(os.path.join(addin_dir, "CounterboreBridging.py"))
    key = next(
        (
            name
            for name, module in list(sys.modules.items())
            if getattr(module, "__file__", None) and os.path.realpath(module.__file__) == main_file
        ),
        None,
    )
    if key is None:
        raise RuntimeError("CounterboreBridging is not loaded in Fusion; start it once in Scripts and Add-Ins")
    old = sys.modules[key]
    loaded_from = os.path.dirname(old.__file__)
    old.stop({})
    for name in [n for n in sys.modules if n == key or n.startswith(key + ".")]:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        key, os.path.join(loaded_from, "CounterboreBridging.py"), submodule_search_locations=[loaded_from]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    module.run({})
    return key


if "ADDIN_DIR" in globals():
    reloaded = reload_addin(ADDIN_DIR)
