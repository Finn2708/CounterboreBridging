from .counterboreBridge import entry as counterbore_bridge

commands = [
    counterbore_bridge,
]


def start():
    for command in commands:
        command.start()


def stop():
    for command in commands:
        command.stop()
