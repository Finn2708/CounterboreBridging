from . import commands
from .lib import fusion360utils as futil


def run(context):
    try:
        commands.start()
    except:
        futil.handle_error("run")


def stop(context):
    try:
        # Stop the commands first: they remove their own event handlers.
        commands.stop()
        futil.clear_handlers()
    except:
        futil.handle_error("stop")
