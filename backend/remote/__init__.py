__all__ = ["RemoteCommandRunner", "RemoteCommandServer"]


def __getattr__(name: str):
    if name == "RemoteCommandRunner":
        from .bridge import RemoteCommandRunner

        return RemoteCommandRunner
    if name == "RemoteCommandServer":
        from .server import RemoteCommandServer

        return RemoteCommandServer
    raise AttributeError(name)
